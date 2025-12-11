"""
Order Monitor Worker
Monitors pending orders and cancels them if momentum is lost
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from webapp.database import SessionLocal, OrderLog, User, ZerodhaCredential
from webapp.zerodha_client import get_zerodha_client
from webapp.encryption import decrypt_api_key, decrypt_access_token
from webapp.order_manager import calculate_price_movement_pct
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Create router for API endpoints
router = APIRouter()

# Global state for monitor
_monitor_running = False
_monitor_task = None


async def monitor_pending_orders_worker(user_id: Optional[str] = None):
    """
    Background worker that monitors pending orders and cancels them if momentum is lost
    
    Checks every 2 minutes during market hours (9:15 AM - 3:30 PM IST)
    
    Args:
        user_id: Optional user ID to monitor (if None, monitors all users)
    """
    global _monitor_running
    
    _monitor_running = True
    logger.info("🔄 Order Monitor Worker started")
    
    while _monitor_running:
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
            from webapp.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Get all pending orders
                query = db.query(OrderLog).filter(OrderLog.status == "PLACED")
                if user_id:
                    query = query.filter(OrderLog.user_id == user_id)
                
                pending_orders = query.all()
                
                if pending_orders:
                    logger.info(f"Checking {len(pending_orders)} pending orders for momentum loss...")
                    
                    for order in pending_orders:
                        try:
                            await check_and_cancel_if_momentum_lost(order, db)
                        except Exception as e:
                            logger.error(f"Error checking order {order.id}: {e}")
                            continue
                else:
                    logger.debug("No pending orders to monitor")
                
            finally:
                db.close()
            
            # Wait 2 minutes before next check
            await asyncio.sleep(120)  # 2 minutes
            
        except Exception as e:
            logger.error(f"Error in order monitor worker: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(300)
    
    logger.info("🛑 Order Monitor Worker stopped")


async def check_and_cancel_if_momentum_lost(order: OrderLog, db: Session):
    """
    Check if an order should be cancelled due to momentum loss
    
    Logic:
    1. Get current price and today's high from Zerodha
    2. Check if price moved favorably (towards target) then came back
    3. If momentum is lost, cancel the order
    
    Args:
        order: OrderLog instance
        db: Database session
    """
    try:
        # Get user credentials
        user = db.query(User).filter(User.id == order.user_id).first()
        if not user:
            logger.warning(f"User not found for order {order.id}")
            return
        
        cred = db.query(ZerodhaCredential).filter(
            ZerodhaCredential.user_id == user.id
        ).first()
        
        if not cred or not cred.is_connected:
            logger.debug(f"User {user.id} not connected to Zerodha, skipping order {order.id}")
            return
        
        # Get Zerodha client
        api_key = decrypt_api_key(cred.api_key)
        access_token = decrypt_access_token(cred.access_token)
        client = get_zerodha_client(user.id, api_key, access_token)
        
        # Get order details from Zerodha
        try:
            orders = client.get_orders()
            zerodha_order = None
            for o in orders:
                if o.get('order_id') == order.order_id:
                    zerodha_order = o
                    break
            
            if not zerodha_order:
                logger.debug(f"Order {order.order_id} not found in Zerodha (may be filled or cancelled)")
                # Update status if order is not found (might be filled)
                order.status = "COMPLETE"
                order.status_message = "Order not found in Zerodha (likely filled)"
                db.commit()
                return
            
            # Check order status
            order_status = zerodha_order.get('status')
            if order_status not in ['OPEN', 'TRIGGER PENDING']:
                # Order is filled, cancelled, or rejected
                logger.debug(f"Order {order.order_id} status: {order_status}, updating...")
                order.status = order_status
                db.commit()
                return
            
            # Order is still pending, check for momentum loss
            # Get current price and today's high
            exchange = order.exchange
            symbol = order.symbol
            
            # Construct instrument token
            instrument_token = f"{exchange}:{symbol}"
            
            # Get quote (has high/low data)
            try:
                quotes = client.get_quote([instrument_token])
                if instrument_token not in quotes:
                    logger.warning(f"Could not get quote for {instrument_token}")
                    return
                
                quote_data = quotes[instrument_token]
                ohlc = quote_data.get('ohlc', {})
                current_price = ohlc.get('last_price') or quote_data.get('last_price')
                today_high = ohlc.get('high') or quote_data.get('day_high') or quote_data.get('high')
                
                if not current_price:
                    logger.warning(f"Could not get current price for {instrument_token}")
                    return
                
            except Exception as e:
                logger.warning(f"Error fetching quote for {instrument_token}: {e}")
                return
            
            # Get order price (LIMIT price)
            order_price = order.price
            if not order_price:
                logger.debug(f"Order {order.id} has no price (MARKET order), skipping momentum check")
                return
            
            # Get target price from order notes or calculate from SL/Target if bracket order
            # For now, we'll use a heuristic: if price moved >5% from order price, check momentum
            target_price = None
            # Try to extract from order notes or use a default (order_price + 10%)
            # In production, you'd store target in OrderLog
            target_price = order_price * 1.10  # Default 10% target
            
            # Check for momentum loss
            if today_high and target_price:
                # Calculate how much price moved towards target
                target_movement_pct = calculate_price_movement_pct(order_price, target_price)
                high_movement_pct = calculate_price_movement_pct(order_price, today_high)
                
                # If price moved >30% towards target, then came back, cancel
                if target_movement_pct > 0:  # Target is above entry (BUY scenario)
                    favorable_movement_threshold = target_movement_pct * 0.3  # 30% of target movement
                    
                    if high_movement_pct > favorable_movement_threshold:
                        # Price moved favorably, check if it came back
                        current_movement_from_high = calculate_price_movement_pct(today_high, current_price)
                        current_movement_from_order = calculate_price_movement_pct(order_price, current_price)
                        
                        # If price is back near order price (within 1%) after moving up
                        if abs(current_movement_from_order) < 1.0 and current_movement_from_high < -3.0:
                            # Momentum lost - cancel the order
                            logger.warning(
                                f"🚨 MOMENTUM LOST: Order {order.id} ({symbol}) - "
                                f"Price moved up {high_movement_pct:+.2f}% (reached ₹{today_high:.2f}) "
                                f"but now back to ₹{current_price:.2f} (near order price ₹{order_price:.2f}). "
                                f"Cancelling order to prevent entering on falling price."
                            )
                            
                            # Cancel order on Zerodha
                            try:
                                client.cancel_order(order.order_id)
                                
                                # Update order status
                                order.status = "CANCELLED"
                                order.status_message = (
                                    f"Momentum lost - price moved up {high_movement_pct:+.2f}% "
                                    f"then fell back. Order cancelled to protect capital."
                                )
                                order.completed_at = datetime.utcnow()
                                db.commit()
                                
                                logger.info(f"✅ Order {order.id} cancelled successfully")
                                
                            except Exception as e:
                                logger.error(f"Error cancelling order {order.id}: {e}")
                                # Still update status to track the issue
                                order.status_message = f"Failed to cancel: {str(e)}"
                                db.commit()
                            
                            return
            
            # No momentum loss detected, order is still valid
            logger.debug(f"Order {order.id} ({symbol}) - No momentum loss detected. "
                        f"Current: ₹{current_price:.2f}, Order: ₹{order_price:.2f}, High: ₹{today_high:.2f}")
            
        except Exception as e:
            logger.error(f"Error checking order {order.id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    except Exception as e:
        logger.error(f"Error in check_and_cancel_if_momentum_lost: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def start_order_monitor(user_id: Optional[str] = None):
    """
    Start the order monitor worker
    
    Args:
        user_id: Optional user ID to monitor (if None, monitors all users)
    """
    global _monitor_task, _monitor_running
    
    if _monitor_running:
        logger.warning("Order monitor is already running")
        return
    
    # Start background task
    import asyncio
    loop = asyncio.get_event_loop()
    _monitor_task = loop.create_task(monitor_pending_orders_worker(user_id))
    
    logger.info("✅ Order Monitor Worker started")


def stop_order_monitor():
    """
    Stop the order monitor worker
    """
    global _monitor_running, _monitor_task
    
    if not _monitor_running:
        logger.warning("Order monitor is not running")
        return
    
    _monitor_running = False
    
    if _monitor_task:
        _monitor_task.cancel()
        _monitor_task = None
    
    logger.info("🛑 Order Monitor Worker stopped")


def is_monitor_running() -> bool:
    """Check if order monitor is running"""
    return _monitor_running


# API Endpoints
@router.get("/status")
async def get_monitor_status():
    """Get order monitor status"""
    return {
        "running": _monitor_running,
        "message": "Order monitor is running" if _monitor_running else "Order monitor is stopped"
    }


@router.post("/start")
async def start_monitor():
    """Start the order monitor worker"""
    if _monitor_running:
        return {"success": False, "message": "Order monitor is already running"}
    
    start_order_monitor()
    return {"success": True, "message": "Order monitor started"}


@router.post("/stop")
async def stop_monitor():
    """Stop the order monitor worker"""
    if not _monitor_running:
        return {"success": False, "message": "Order monitor is not running"}
    
    stop_order_monitor()
    return {"success": True, "message": "Order monitor stopped"}

