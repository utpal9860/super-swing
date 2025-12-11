"""
SL Placement Worker
Places stop loss orders after entry orders are filled (non-blocking)
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from webapp.database import SessionLocal, OrderLog, User, ZerodhaCredential
from webapp.zerodha_client import get_zerodha_client
from webapp.encryption import decrypt_api_key, decrypt_access_token
from webapp.order_manager import (
    is_option_symbol, get_option_exchange, get_product_type_for_option,
    get_product_type_for_stock, extract_underlying_from_option_symbol
)
from webapp.utils.options import get_option_lot_size
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Create router for API endpoints
router = APIRouter()

# Global state for SL placement worker
_sl_placement_running = False
_sl_placement_task = None


def calculate_auto_sl(
    entry_price: float,
    is_option: bool = True,
    days_to_expiry: Optional[int] = None
) -> Optional[float]:
    """
    Calculate automatic stop loss when not provided
    
    Based on backtest analysis:
    - Monthly options: 30% SL
    - Weekly options (≤7 days): 40% SL
    
    Args:
        entry_price: Entry price
        is_option: True if option, False if stock
        days_to_expiry: Days until expiry (optional)
        
    Returns:
        Calculated SL price or None
    """
    if is_option:
        # Option-specific SL calculation
        if days_to_expiry and days_to_expiry <= 7:
            sl_percentage = 40.0  # Weekly expiry - higher volatility
        else:
            sl_percentage = 30.0  # Monthly expiry
        
        sl_price = entry_price * (1 - sl_percentage / 100)
        
        # Minimum 25% SL (safety net)
        min_sl = entry_price * 0.75
        return max(sl_price, min_sl)
    else:
        # Stock: 4% SL
        return entry_price * 0.96


async def place_sl_order_with_retry(
    client,
    symbol: str,
    exchange: str,
    quantity: int,
    sl_price: float,
    product: str,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> Optional[str]:
    """
    Place SL order with automatic retry on failure
    
    Args:
        client: Zerodha client instance
        symbol: Trading symbol
        exchange: Exchange (NSE/BSE/NFO/BFO)
        quantity: Quantity
        sl_price: Stop loss price
        product: Product type (CNC/NRML)
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries (seconds)
        
    Returns:
        Order ID if successful, None if all retries fail
    """
    for attempt in range(1, max_retries + 1):
        try:
            result = client.place_order(
                symbol=symbol,
                exchange=exchange,
                transaction_type="SELL",  # SL is a sell order
                quantity=quantity,
                order_type="SL",  # Stop Loss order type
                price=sl_price,
                trigger_price=sl_price,
                product=product,
                validity="DAY"
            )
            order_id = result.get("order_id")
            if order_id:
                logger.info(f"SL order placed successfully on attempt {attempt}: {order_id}")
                return order_id
        except Exception as e:
            logger.warning(f"SL order placement attempt {attempt} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to place SL order after {max_retries} attempts")
    
    return None


async def sl_placement_worker(user_id: Optional[str] = None):
    """
    Background worker that places SL orders for filled entry orders
    
    Checks every 30 seconds during market hours (9:15 AM - 3:30 PM IST)
    
    Args:
        user_id: Optional user ID to monitor (if None, monitors all users)
    """
    global _sl_placement_running
    
    _sl_placement_running = True
    logger.info("🔄 SL Placement Worker started")
    
    while _sl_placement_running:
        try:
            # Check if market is open (9:15 AM - 3:30 PM IST)
            now = datetime.now()
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            
            if now < market_open or now > market_close:
                # Market closed, wait 30 minutes and check again
                logger.debug("Market closed, waiting 30 minutes...")
                await asyncio.sleep(1800)  # 30 minutes
                continue
            
            # Get database session
            db = SessionLocal()
            
            try:
                # Get all users with Zerodha credentials
                users_query = db.query(User).join(ZerodhaCredential).filter(ZerodhaCredential.is_connected == True)
                if user_id:
                    users_query = users_query.filter(User.id == user_id)
                
                users = users_query.all()
                
                for user in users:
                    try:
                        await check_and_place_sl_orders(user, db)
                    except Exception as e:
                        logger.error(f"Error checking SL orders for user {user.id}: {e}")
                        continue
                
            finally:
                db.close()
            
            # Wait 30 seconds before next check
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in SL placement worker: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)
    
    logger.info("🛑 SL Placement Worker stopped")


async def check_and_place_sl_orders(user: User, db: Session):
    """
    Check for filled orders without SL and place SL orders
    
    Args:
        user: User instance
        db: Database session
    """
    try:
        # Get Zerodha credentials
        cred = db.query(ZerodhaCredential).filter(
            ZerodhaCredential.user_id == user.id
        ).first()
        
        if not cred or not cred.is_connected:
            return
        
        # Get Zerodha client
        api_key = decrypt_api_key(cred.api_key)
        access_token = decrypt_access_token(cred.access_token)
        client = get_zerodha_client(user.id, api_key, access_token)
        
        # Get all PLACED orders for this user (entry orders)
        placed_orders = db.query(OrderLog).filter(
            OrderLog.user_id == user.id,
            OrderLog.status == "PLACED",
            OrderLog.transaction_type == "BUY"
        ).all()
        
        for order_log in placed_orders:
            try:
                # Check if order is filled on Zerodha
                orders = client.get_orders()
                zerodha_order = None
                for o in orders:
                    if o.get('order_id') == order_log.order_id:
                        zerodha_order = o
                        break
                
                if not zerodha_order:
                    continue
                
                order_status = zerodha_order.get('status')
                
                # Check if order is filled
                if order_status == 'COMPLETE' and order_log.filled_quantity > 0:
                    # Order is filled - check if SL order exists
                    # Look for SL order in trade data
                    from webapp.api.paper_trading import load_trades
                    trades = load_trades(user.id)
                    
                    # Find trade by order ID
                    trade = None
                    for t in trades:
                        if t.get('zerodha_buy_order_id') == order_log.order_id:
                            trade = t
                            break
                    
                    if not trade:
                        continue
                    
                    # Check if SL order already placed
                    if trade.get('zerodha_sl_order_id'):
                        continue
                    
                    # Check if SL is set
                    sl_price = trade.get('stop_loss', 0)
                    if not sl_price or sl_price == 0:
                        # Auto-calculate SL
                        entry_price = float(trade.get('entry_price', 0))
                        is_option = trade.get('instrument_type') == 'option'
                        
                        # Calculate days to expiry if available
                        days_to_expiry = None
                        expiry_month = trade.get('option_expiry_month')
                        if expiry_month:
                            try:
                                expiry_date = datetime.strptime(expiry_month, '%d-%b-%Y')
                                days_to_expiry = (expiry_date - datetime.now()).days
                            except:
                                pass
                        
                        sl_price = calculate_auto_sl(
                            entry_price=entry_price,
                            is_option=is_option,
                            days_to_expiry=days_to_expiry
                        )
                        
                        if not sl_price:
                            continue
                        
                        # Update trade with calculated SL
                        trade['stop_loss'] = sl_price
                        from webapp.api.paper_trading import save_trades
                        save_trades(user.id, trades)
                    
                    # Place SL order
                    symbol = order_log.symbol
                    exchange = order_log.exchange
                    quantity = order_log.filled_quantity or order_log.quantity
                    product = order_log.product
                    
                    sl_order_id = await place_sl_order_with_retry(
                        client=client,
                        symbol=symbol,
                        exchange=exchange,
                        quantity=quantity,
                        sl_price=sl_price,
                        product=product,
                        max_retries=3,
                        retry_delay=2.0
                    )
                    
                    if sl_order_id:
                        # Update trade with SL order ID
                        trade['zerodha_sl_order_id'] = sl_order_id
                        from webapp.api.paper_trading import save_trades
                        save_trades(user.id, trades)
                        
                        logger.info(f"✅ SL order placed for trade {trade.get('id')}: {sl_order_id} at ₹{sl_price:.2f}")
                    else:
                        logger.warning(f"⚠️  Failed to place SL order for trade {trade.get('id')} after retries")
                
            except Exception as e:
                logger.error(f"Error processing order {order_log.id}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Error in check_and_place_sl_orders: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def start_sl_placement_worker(user_id: Optional[str] = None):
    """
    Start the SL placement worker
    
    Args:
        user_id: Optional user ID to monitor (if None, monitors all users)
    """
    global _sl_placement_task, _sl_placement_running
    
    if _sl_placement_running:
        logger.warning("SL placement worker is already running")
        return
    
    # Start background task
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    _sl_placement_task = loop.create_task(sl_placement_worker(user_id))
    
    logger.info("✅ SL Placement Worker started")


def stop_sl_placement_worker():
    """
    Stop the SL placement worker
    """
    global _sl_placement_running, _sl_placement_task
    
    if not _sl_placement_running:
        logger.warning("SL placement worker is not running")
        return
    
    _sl_placement_running = False
    
    if _sl_placement_task:
        _sl_placement_task.cancel()
        _sl_placement_task = None
    
    logger.info("🛑 SL Placement Worker stopped")


def is_sl_placement_running() -> bool:
    """Check if SL placement worker is running"""
    return _sl_placement_running


# API Endpoints
@router.get("/status")
async def get_sl_placement_status():
    """Get SL placement worker status"""
    return {
        "running": _sl_placement_running,
        "message": "SL placement worker is running" if _sl_placement_running else "SL placement worker is stopped"
    }


@router.post("/start")
async def start_sl_placement():
    """Start the SL placement worker"""
    if _sl_placement_running:
        return {"success": False, "message": "SL placement worker is already running"}
    
    start_sl_placement_worker()
    return {"success": True, "message": "SL placement worker started"}


@router.post("/stop")
async def stop_sl_placement():
    """Stop the SL placement worker"""
    if not _sl_placement_running:
        return {"success": False, "message": "SL placement worker is not running"}
    
    stop_sl_placement_worker()
    return {"success": True, "message": "SL placement worker stopped"}

