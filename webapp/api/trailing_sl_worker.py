"""
Trailing Stop Loss Worker
Monitors open positions and automatically updates stop loss as price moves favorably
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from webapp.database import SessionLocal, OrderLog, User, ZerodhaCredential
from webapp.zerodha_client import get_zerodha_client
from webapp.encryption import decrypt_api_key, decrypt_access_token
from webapp.api.paper_trading import load_trades, save_trades
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Create router for API endpoints
router = APIRouter()

# Global state for trailing SL worker
_trailing_sl_running = False
_trailing_sl_task = None


async def trailing_sl_worker(user_id: Optional[str] = None):
    """
    Background worker that monitors open positions and updates trailing stop loss
    
    Checks every 1 minute during market hours (9:15 AM - 3:30 PM IST)
    
    Args:
        user_id: Optional user ID to monitor (if None, monitors all users)
    """
    global _trailing_sl_running
    
    _trailing_sl_running = True
    logger.info("🔄 Trailing Stop Loss Worker started")
    
    while _trailing_sl_running:
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
                # Get all users with open trades
                from webapp.database import User
                users = db.query(User).all()
                if user_id:
                    users = [u for u in users if u.id == user_id]
                
                for user in users:
                    try:
                        await check_and_update_trailing_sl(user, db)
                    except Exception as e:
                        logger.error(f"Error checking trailing SL for user {user.id}: {e}")
                        continue
                
            finally:
                db.close()
            
            # Wait 1 minute before next check
            await asyncio.sleep(60)  # 1 minute
            
        except Exception as e:
            logger.error(f"Error in trailing SL worker: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)
    
    logger.info("🛑 Trailing Stop Loss Worker stopped")


async def check_and_update_trailing_sl(user: User, db: Session):
    """
    Check and update trailing stop loss for a user's open positions
    
    Args:
        user: User instance
        db: Database session
    """
    try:
        # Get user's open trades
        trades = load_trades(user.id)
        open_trades = [t for t in trades if t.get('status') == 'open' and t.get('is_live')]
        
        if not open_trades:
            return
        
        # Get Zerodha credentials
        cred = db.query(ZerodhaCredential).filter(
            ZerodhaCredential.user_id == user.id
        ).first()
        
        if not cred or not cred.is_connected:
            logger.debug(f"User {user.id} not connected to Zerodha, skipping trailing SL check")
            return
        
        # Get Zerodha client
        api_key = decrypt_api_key(cred.api_key)
        access_token = decrypt_access_token(cred.access_token)
        client = get_zerodha_client(user.id, api_key, access_token)
        
        # Get current positions from Zerodha
        try:
            positions = client.get_positions()
            net_positions = positions.get('net', [])
            
            # Create a map of symbol -> position
            position_map = {}
            for pos in net_positions:
                symbol = pos.get('tradingsymbol')
                if symbol:
                    position_map[symbol] = pos
            
        except Exception as e:
            logger.warning(f"Could not fetch positions from Zerodha for user {user.id}: {e}")
            return
        
        # Check each open trade
        for trade in open_trades:
            try:
                await update_trailing_sl_for_trade(trade, client, position_map, user.id, db)
            except Exception as e:
                logger.error(f"Error updating trailing SL for trade {trade.get('id')}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Error in check_and_update_trailing_sl: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


async def update_trailing_sl_for_trade(
    trade: Dict,
    client,
    position_map: Dict,
    user_id: str,
    db: Session
):
    """
    Update trailing stop loss for a single trade
    
    Args:
        trade: Trade dictionary
        client: Zerodha client
        position_map: Map of symbol -> position from Zerodha
        user_id: User ID
        db: Database session
    """
    try:
        # Check if trailing is enabled
        if not trade.get('trailing_enabled'):
            return
        
        # Get trade details
        symbol = trade.get('symbol', '').replace('.NS', '')
        entry_price = float(trade.get('entry_price', 0))
        current_sl = float(trade.get('stop_loss', 0))
        trailing_distance_pct = float(trade.get('trailing_distance', 3.0))
        highest_price = float(trade.get('highest_price', entry_price))
        
        # Get current price from Zerodha
        # For options, need to construct symbol
        is_option = trade.get('instrument_type') == 'option'
        
        if is_option:
            # Construct option symbol
            from webapp.api.eod_monitor import construct_nse_option_symbol
            strike = float(trade.get('option_strike', 0))
            option_type = trade.get('option_type', 'CE')
            expiry_month = trade.get('option_expiry_month')
            
            if not expiry_month:
                return
            
            option_symbol = construct_nse_option_symbol(symbol, strike, option_type, expiry_month)
            if not option_symbol:
                return
            
            # Determine exchange
            from webapp.order_manager import get_option_exchange
            exchange = get_option_exchange(option_symbol)
            instrument_token = f"{exchange}:{option_symbol}"
        else:
            # For stocks
            exchange = trade.get('exchange', 'NSE')
            instrument_token = f"{exchange}:{symbol}"
        
        # Get current price
        try:
            quotes = client.get_quote([instrument_token])
            if instrument_token not in quotes:
                return
            
            quote_data = quotes[instrument_token]
            ohlc = quote_data.get('ohlc', {})
            current_price = ohlc.get('last_price') or quote_data.get('last_price')
            
            if not current_price:
                return
            
        except Exception as e:
            logger.warning(f"Could not get current price for {instrument_token}: {e}")
            return
        
        # Update highest price
        if current_price > highest_price:
            highest_price = current_price
            trade['highest_price'] = highest_price
        
        # Calculate new trailing SL
        # For BUY: SL = highest_price - (trailing_distance_pct% of highest_price)
        new_sl = highest_price * (1 - trailing_distance_pct / 100)
        
        # Only update if new SL is higher than current SL (trailing up only)
        if new_sl > current_sl:
            # Update stop loss
            trade['stop_loss'] = new_sl
            trade['sl_updates_count'] = trade.get('sl_updates_count', 0) + 1
            trade['last_sl_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Update SL order on Zerodha if we have order ID
            sl_order_id = trade.get('zerodha_sl_order_id')
            if sl_order_id:
                try:
                    # Modify the SL order
                    client.modify_order(
                        order_id=sl_order_id,
                        trigger_price=new_sl,
                        price=new_sl,
                        variety="regular"
                    )
                    
                    logger.info(
                        f"✅ Trailing SL updated for {symbol}: "
                        f"SL moved from ₹{current_sl:.2f} to ₹{new_sl:.2f} "
                        f"(highest: ₹{highest_price:.2f}, current: ₹{current_price:.2f})"
                    )
                    
                except Exception as e:
                    logger.warning(f"Could not modify SL order {sl_order_id} on Zerodha: {e}")
                    # Still update in trade data
            else:
                logger.debug(f"No SL order ID for trade {trade.get('id')}, updated in trade data only")
            
            # Save updated trade
            trades = load_trades(user_id)
            for i, t in enumerate(trades):
                if t.get('id') == trade.get('id'):
                    trades[i] = trade
                    break
            save_trades(user_id, trades)
    
    except Exception as e:
        logger.error(f"Error in update_trailing_sl_for_trade: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def start_trailing_sl_worker(user_id: Optional[str] = None):
    """
    Start the trailing SL worker
    
    Args:
        user_id: Optional user ID to monitor (if None, monitors all users)
    """
    global _trailing_sl_task, _trailing_sl_running
    
    if _trailing_sl_running:
        logger.warning("Trailing SL worker is already running")
        return
    
    # Start background task
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    _trailing_sl_task = loop.create_task(trailing_sl_worker(user_id))
    
    logger.info("✅ Trailing Stop Loss Worker started")


def stop_trailing_sl_worker():
    """
    Stop the trailing SL worker
    """
    global _trailing_sl_running, _trailing_sl_task
    
    if not _trailing_sl_running:
        logger.warning("Trailing SL worker is not running")
        return
    
    _trailing_sl_running = False
    
    if _trailing_sl_task:
        _trailing_sl_task.cancel()
        _trailing_sl_task = None
    
    logger.info("🛑 Trailing Stop Loss Worker stopped")


def is_trailing_sl_running() -> bool:
    """Check if trailing SL worker is running"""
    return _trailing_sl_running


# API Endpoints
@router.get("/status")
async def get_trailing_sl_status():
    """Get trailing SL worker status"""
    return {
        "running": _trailing_sl_running,
        "message": "Trailing SL worker is running" if _trailing_sl_running else "Trailing SL worker is stopped"
    }


@router.post("/start")
async def start_trailing_sl():
    """Start the trailing SL worker"""
    if _trailing_sl_running:
        return {"success": False, "message": "Trailing SL worker is already running"}
    
    start_trailing_sl_worker()
    return {"success": True, "message": "Trailing SL worker started"}


@router.post("/stop")
async def stop_trailing_sl():
    """Stop the trailing SL worker"""
    if not _trailing_sl_running:
        return {"success": False, "message": "Trailing SL worker is not running"}
    
    stop_trailing_sl_worker()
    return {"success": True, "message": "Trailing SL worker stopped"}

