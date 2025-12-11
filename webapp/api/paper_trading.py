"""
Paper Trading API
Handles virtual trades with P&L tracking
**NOW WITH USER AUTHENTICATION & USER-SPECIFIC TRADES**
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Data storage
DATA_DIR = Path(__file__).parent.parent / "data"
BROKERAGE_PER_TRADE = 20.0  # ₹20 per trade (buy or sell)


def get_user_trades_file(user_id: str) -> Path:
    """Get user-specific trades file path"""
    user_data_dir = DATA_DIR / "users" / user_id
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return user_data_dir / "trades.json"


class Trade(BaseModel):
    """Trade model"""
    id: str
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    stop_loss: float
    target: float
    position_value: float
    status: str  # open, closed
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # target, stop_loss, manual, supertrend_sell
    gross_pnl: Optional[float] = None
    brokerage: float = 0.0
    net_pnl: Optional[float] = None
    pct_change: Optional[float] = None
    notes: Optional[str] = None
    # Live trading fields
    is_live: bool = False  # True if placed on Zerodha, False if paper trade
    zerodha_buy_order_id: Optional[str] = None  # Zerodha order ID for buy
    zerodha_sl_order_id: Optional[str] = None  # Zerodha order ID for SL
    zerodha_target_order_id: Optional[str] = None  # Zerodha order ID for target
    user_id: str  # User who owns this trade
    # Trailing stop-loss fields
    trailing_enabled: bool = False  # Enable trailing SL
    trailing_type: str = 'percentage'  # percentage, fixed, atr
    trailing_distance: float = 3.0  # 3% for percentage, ₹3 for fixed, 2x for ATR
    highest_price: Optional[float] = None  # Track highest price since entry
    initial_sl: Optional[float] = None  # Original SL for reference
    sl_updates_count: int = 0  # Number of times SL was trailed
    last_sl_update: Optional[str] = None  # Timestamp of last trail
    last_price_check: Optional[str] = None  # Last time price was checked
    # Option-specific fields (optional, for NFO options)
    instrument_type: Optional[str] = None  # 'option' or None
    option_symbol: Optional[str] = None
    option_type: Optional[str] = None  # CE/PE
    option_strike: Optional[float] = None
    option_expiry_month: Optional[str] = None
    lot_size: Optional[int] = None
    # Telegram message tracking (for reply message handling)
    telegram_message_id: Optional[int] = None  # Original signal message ID
    telegram_channel_id: Optional[int] = None  # Channel/chat ID
    telegram_channel_name: Optional[str] = None  # Channel name


def load_trades(user_id: str) -> List[dict]:
    """Load trades from user-specific JSON file"""
    trades_file = get_user_trades_file(user_id)
    if not trades_file.exists():
        return []
    try:
        with open(trades_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading trades for user {user_id}: {e}")
        return []


def save_trades(user_id: str, trades: List[dict]):
    """Save trades to user-specific JSON file"""
    try:
        trades_file = get_user_trades_file(user_id)
        with open(trades_file, 'w') as f:
            json.dump(trades, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving trades for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save trades: {e}")


# Import auth dependency
from webapp.api.auth_api import get_current_user
from webapp.database import User


@router.get("/all")
async def get_all_trades(current_user: User = Depends(get_current_user)):
    """Get all paper trades for current user"""
    trades = load_trades(current_user.id)
    return {"success": True, "trades": trades, "count": len(trades)}


@router.get("/open")
async def get_open_trades(current_user: User = Depends(get_current_user)):
    """Get open paper trades for current user"""
    trades = load_trades(current_user.id)
    open_trades = [t for t in trades if t['status'] == 'open']
    
    # Recalculate position_value for options to ensure it's correct (entry_price * lot_size * shares)
    for trade in open_trades:
        if trade.get('instrument_type') == 'option':
            entry_price = float(trade.get('entry_price', 0))
            shares = int(trade.get('shares', 1))
            lot_size = trade.get('lot_size')
            
            # If lot_size is missing or 1, try to look it up
            if not lot_size or lot_size == 1:
                try:
                    symbol = trade.get('symbol', '').replace('.NS', '')
                    lot_size = get_option_lot_size(symbol)
                except Exception:
                    lot_size = 1
            
            # Recalculate position_value
            trade['position_value'] = entry_price * int(lot_size) * shares
    
    return {"success": True, "trades": open_trades, "count": len(open_trades)}


@router.get("/closed")
async def get_closed_trades(current_user: User = Depends(get_current_user)):
    """Get closed paper trades for current user"""
    trades = load_trades(current_user.id)
    closed_trades = [t for t in trades if t['status'] == 'closed']
    return {"success": True, "trades": closed_trades, "count": len(closed_trades)}


@router.get("/summary")
async def get_trades_summary(current_user: User = Depends(get_current_user)):
    """Get summary statistics of all trades for current user"""
    trades = load_trades(current_user.id)
    
    if not trades:
        return {
            "success": True,
            "total_trades": 0,
            "open_trades": 0,
            "closed_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_invested": 0,
            "gross_pnl": 0,
            "total_brokerage": 0,
            "net_pnl": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "expectancy": 0,
            "profit_factor": 0
        }
    
    closed_trades = [t for t in trades if t['status'] == 'closed']
    open_trades = [t for t in trades if t['status'] == 'open']
    
    # Calculate total_invested (Active Capital)
    # For options: entry_price * lot_size * shares
    # For equities: entry_price * shares (or use position_value if already correct)
    total_invested = 0
    for t in open_trades:
        if t.get('instrument_type') == 'option':
            # Recalculate position_value for options based on lot_size
            entry_price = float(t.get('entry_price', 0))
            shares = int(t.get('shares', 1))
            lot_size = t.get('lot_size')
            
            # If lot_size is missing or 1, try to look it up
            if not lot_size or lot_size == 1:
                try:
                    symbol = t.get('symbol', '').replace('.NS', '')
                    lot_size = get_option_lot_size(symbol)
                except Exception:
                    lot_size = 1
            
            # Position value = entry_price * lot_size * shares
            position_value = entry_price * int(lot_size) * shares
            total_invested += position_value
        else:
            # For equities, use stored position_value or calculate
            position_value = t.get('position_value')
            if not position_value:
                entry_price = float(t.get('entry_price', 0))
                shares = int(t.get('shares', 1))
                position_value = entry_price * shares
            total_invested += float(position_value)
    gross_pnl = sum(t.get('gross_pnl', 0) for t in closed_trades)
    total_brokerage = sum(t.get('brokerage', 0) for t in trades)
    net_pnl = sum(t.get('net_pnl', 0) for t in closed_trades)
    
    winning_trades = [t for t in closed_trades if t.get('net_pnl', 0) > 0]
    losing_trades = [t for t in closed_trades if t.get('net_pnl', 0) < 0]
    
    win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
    avg_win = (sum(t['net_pnl'] for t in winning_trades) / len(winning_trades)) if winning_trades else 0
    avg_loss = (sum(t['net_pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
    
    return {
        "success": True,
        "total_trades": len(trades),
        "open_trades": len(open_trades),
        "closed_trades": len(closed_trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "total_invested": round(total_invested, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_brokerage": round(total_brokerage, 2),
        "net_pnl": round(net_pnl, 2),
        "win_rate": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round((avg_win * win_rate/100) + (avg_loss * (100-win_rate)/100), 2) if closed_trades else 0
    }

from fastapi import Body, Depends
from sqlalchemy.orm import Session
from webapp.utils.options import get_option_ltp, get_option_lot_size
from webapp.database import get_db, User as DbUser
import os
import logging

logger = logging.getLogger(__name__)


class SignalOrder(BaseModel):
    action: str  # BUY/SELL
    symbol: str  # e.g., ASHOKLEY
    strike: float
    option_type: str  # CE/PE
    trigger_type: str  # ABOVE/BELOW
    trigger_price: float
    targets: Optional[List[float]] = None
    stop_loss_text: Optional[str] = None  # 'PAID' or number as string
    expiry_month: Optional[str] = None  # e.g., DECEMBER
    quantity: Optional[int] = 1
    notes: Optional[str] = None
    # Optional routing to a specific user (used with service API key/bypass)
    for_user_id: Optional[str] = None
    for_username: Optional[str] = None
    # Telegram message tracking (for reply message handling)
    telegram_message_id: Optional[int] = None  # Original signal message ID
    telegram_channel_id: Optional[int] = None  # Channel/chat ID
    telegram_channel_name: Optional[str] = None  # Channel name


@router.post("/create_from_signal")
async def create_trade_from_signal(
    signal: SignalOrder,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a paper trade from a parsed Telegram signal (options).
    Fetches current option LTP for entry price.
    """
    # CRITICAL SAFETY CHECK: For weekly index contracts, require explicit expiry date
    from webapp.utils.options import INDEX_SYMBOLS, INDEX_EXPIRY_SCHEDULE
    
    symbol_upper = signal.symbol.upper().replace(".NS", "")
    is_index = symbol_upper in INDEX_SYMBOLS
    is_expiry_date_format = signal.expiry_month and '-' in signal.expiry_month
    is_month_name_only = signal.expiry_month and not is_expiry_date_format
    
    # Check if this is a weekly index contract
    if is_index:
        expiry_day, expiry_type = INDEX_EXPIRY_SCHEDULE.get(symbol_upper, (0, 'monthly'))
        is_weekly_index = expiry_type == 'weekly'
        
        # For weekly index contracts, explicit date is REQUIRED for safety
        if is_weekly_index and not is_expiry_date_format:
            error_msg = (
                f"SAFETY REJECTION: {symbol_upper} is a weekly index contract. "
                f"Explicit expiry date (e.g., '11 December') is REQUIRED, but only month name "
                f"('{signal.expiry_month}') or no expiry was provided. "
                f"Weekly contracts expire every week, so we cannot determine which weekly expiry "
                f"to use without an explicit date. Trade rejected for safety."
            )
            logger.warning(error_msg)
            print(f"⚠️ {error_msg}")
            
            return {
                "success": False,
                "message": error_msg,
                "rejected": True,
                "reason": "weekly_index_missing_explicit_expiry"
            }
    
    # Fetch option LTP
    result = get_option_ltp(
        symbol=signal.symbol,
        strike=signal.strike,
        option_type=signal.option_type,
        expiry_month=signal.expiry_month
    )
    # Handle return value (always returns 4 values: ltp, resolved_expiry, today_high, today_low)
    if len(result) == 2:
        ltp, resolved_expiry = result
    else:
        ltp, resolved_expiry, _, _ = result
    # Fallback: if LTP not available (API blocked or symbol mismatch), use trigger price
    used_fallback_price = False
    if ltp is None:
        ltp = float(signal.trigger_price)
        used_fallback_price = True
    
    # Always try to resolve expiry date to date format (e.g., "30-Dec-2025")
    # This ensures we store a date format, not just month name
    if is_expiry_date_format:
        # Expiry is already in date format - use it directly!
        resolved_expiry = signal.expiry_month
        
        # Validate the explicit date for weekly index contracts
        # For SENSEX: Should be Thursday or previous trading day if Thursday was a holiday
        if is_index:
            expiry_day, expiry_type = INDEX_EXPIRY_SCHEDULE.get(symbol_upper, (0, 'monthly'))
            if expiry_type == 'weekly':
                # Validate that the date is a valid weekly expiry
                from webapp.utils.options import validate_expiry_for_order
                is_valid, error_msg, suggested = validate_expiry_for_order(
                    symbol=signal.symbol,
                    expiry_date_str=resolved_expiry,
                    strike=signal.strike,
                    option_type=signal.option_type
                )
                if not is_valid:
                    logger.warning(f"⚠️ Explicit expiry date validation warning for {signal.symbol}: {error_msg}")
                    if suggested:
                        logger.info(f"💡 Suggested correct expiry: {suggested}")
                    # Still use the provided date - user provided it explicitly, so trust it
                    # (they might know about special holiday adjustments)
        
        logger.info(f"Using explicit expiry date from signal: {signal.symbol} -> {resolved_expiry}")
    elif not resolved_expiry:
        # Only calculate if not already resolved and not in date format
        # Note: For weekly indices, this should not happen (already rejected above)
        # This is only for stocks (monthly) or monthly indices
        try:
            from webapp.utils.options import calculate_option_expiry
            resolved_expiry = calculate_option_expiry(
                symbol=signal.symbol,
                expiry_month=signal.expiry_month
            )
            if resolved_expiry:
                logger.info(f"Calculated expiry for {signal.symbol}: {signal.expiry_month} -> {resolved_expiry}")
        except Exception as e:
            logger.warning(f"Failed to calculate expiry for {signal.symbol}: {e}")
            # If it fails, we'll store the month name and calculate it later in EOD

    # Resolve stop loss
    if signal.stop_loss_text and signal.stop_loss_text.upper() != "PAID":
        try:
            stop_loss_val = float(signal.stop_loss_text)
        except:
            stop_loss_val = 0.0
    else:
        # AUTO-CALCULATE SL when not provided (based on backtest analysis)
        entry_price = float(ltp)
        
        # Check if this is a weekly contract
        from webapp.utils.options import INDEX_SYMBOLS, INDEX_EXPIRY_SCHEDULE
        symbol_upper = signal.symbol.upper()
        is_index = symbol_upper in INDEX_SYMBOLS
        is_weekly = False
        days_to_expiry = None
        
        if is_index:
            expiry_day, expiry_type = INDEX_EXPIRY_SCHEDULE.get(symbol_upper, (0, 'monthly'))
            is_weekly = expiry_type == 'weekly'
        
        # Calculate days to expiry if we have expiry info
        if resolved_expiry:
            try:
                expiry_date = datetime.strptime(resolved_expiry, '%d-%b-%Y')
                days_to_expiry = (expiry_date - datetime.now()).days
            except:
                pass
        
        # Determine SL percentage based on expiry type and days to expiry
        if is_weekly or (days_to_expiry and days_to_expiry <= 7):
            # Weekly options or options expiring in ≤7 days: 40% SL (higher volatility)
            sl_percentage = 40.0
        else:
            # Monthly options: 30% SL (based on backtest recommendation)
            sl_percentage = 30.0
        
        stop_loss_val = entry_price * (1 - sl_percentage / 100)
        
        # Minimum safety: Never less than 25% SL (absolute minimum)
        min_sl = entry_price * 0.75
        stop_loss_val = max(stop_loss_val, min_sl)
        
        logger.info(f"Auto-calculated SL: ₹{stop_loss_val:.2f} ({sl_percentage}% below entry ₹{entry_price:.2f}, "
                   f"weekly={is_weekly}, days_to_expiry={days_to_expiry})")

    # Resolve target (first target if multiple)
    target_val = float(signal.targets[0]) if signal.targets else 0.0

    # Determine owner user id (route to specific user if requested and caller is service/local)
    owner_user_id = current_user.id
    if (getattr(current_user, "username", "") in ("service", "local")):
        target_user: Optional[DbUser] = None
        # 1) explicit routing from payload
        if signal.for_user_id:
            target_user = db.query(DbUser).filter(DbUser.id == signal.for_user_id).first()
        if not target_user and signal.for_username:
            target_user = db.query(DbUser).filter(DbUser.username == signal.for_username).first()
        # 2) fallback to env default user (SERVICE_DEFAULT_USER_USERNAME)
        if not target_user:
            default_user = os.environ.get("SERVICE_DEFAULT_USER_USERNAME", "").strip()
            if default_user:
                target_user = db.query(DbUser).filter(DbUser.username == default_user).first()
        if target_user:
            owner_user_id = target_user.id
            logger.info(f"Routing signal trade to user {target_user.username} ({target_user.id})")
        else:
            logger.warning("Signal routing: no target user matched; saving under service/local user")

    # Resolve lot size for options
    lot_size_val = 1
    try:
        lot_size_val = get_option_lot_size(signal.symbol)
    except Exception:
        lot_size_val = 1

    # Build trade
    trade = Trade(
        id=f"TRADE_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        symbol=f"{signal.symbol}.NS",  # store underlying equity symbol
        entry_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        entry_price=float(ltp),
        shares=signal.quantity or 1,
        stop_loss=stop_loss_val,
        target=target_val,
        position_value=float(ltp) * (signal.quantity or 1) * lot_size_val,
        status="open",
        brokerage=20.0,
        user_id=owner_user_id,
        instrument_type="option",
        option_symbol=f"{signal.symbol} {int(signal.strike)} {signal.option_type}",
        option_type=signal.option_type,
        option_strike=float(signal.strike),
        # Always prefer resolved_expiry (date format like "30-Dec-2025") over month name
        # If resolved_expiry is None, store expiry_month (month name) - it will be resolved in EOD
        option_expiry_month=resolved_expiry if resolved_expiry else signal.expiry_month,
        lot_size=lot_size_val,
        telegram_message_id=signal.telegram_message_id,
        telegram_channel_id=signal.telegram_channel_id,
        telegram_channel_name=signal.telegram_channel_name,
        notes=(signal.notes or f"Telegram signal: {signal.dict()}") + (", entry=fallback_trigger_price" if used_fallback_price else "")
    )

    trades = load_trades(owner_user_id)
    trades.append(trade.dict())
    save_trades(owner_user_id, trades)

    return {
        "success": True,
        "message": "Trade created from signal",
        "trade": trade.dict(),
        "saved_for_user_id": owner_user_id
    }


@router.post("/create")
async def create_trade(trade: Trade, current_user: User = Depends(get_current_user)):
    """Create a new paper trade for current user"""
    trades = load_trades(current_user.id)
    
    # Check if trade ID already exists
    if any(t['id'] == trade.id for t in trades):
        raise HTTPException(status_code=400, detail="Trade ID already exists")
    
    # Add entry brokerage and user_id
    trade.brokerage = BROKERAGE_PER_TRADE
    trade.user_id = current_user.id
    
    trade_dict = trade.dict()
    trades.append(trade_dict)
    save_trades(current_user.id, trades)
    
    logger.info(f"Created new trade for user {current_user.username}: {trade.symbol} - {trade.shares} shares @ ₹{trade.entry_price}")
    
    return {"success": True, "message": "Trade created successfully", "trade": trade_dict}


@router.put("/close/{trade_id}")
async def close_trade(
    trade_id: str,
    exit_price: float,
    exit_reason: str,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Close an open paper trade for current user"""
    trades = load_trades(current_user.id)
    
    trade = next((t for t in trades if t['id'] == trade_id), None)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade['status'] == 'closed':
        raise HTTPException(status_code=400, detail="Trade already closed")
    
    # Update trade
    trade['status'] = 'closed'
    trade['exit_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    trade['exit_price'] = exit_price
    trade['exit_reason'] = exit_reason
    trade['notes'] = notes
    
    # Calculate P&L - account for lot_size for options
    entry_price = float(trade['entry_price'])
    shares = int(trade.get('shares', 1) or 1)
    
    # For options, use lot_size; for equity, just use shares
    is_option = trade.get('instrument_type') == 'option'
    if is_option:
        # Look up lot_size if missing from trade data (for older trades)
        lot_size = trade.get('lot_size')
        if not lot_size or lot_size == 1:
            try:
                lot_size = get_option_lot_size(trade.get('symbol', '').replace('.NS', ''))
            except Exception:
                lot_size = 1
        effective_qty = shares * int(lot_size)
    else:
        effective_qty = shares
    
    trade['gross_pnl'] = (exit_price - entry_price) * effective_qty
    trade['brokerage'] = BROKERAGE_PER_TRADE * 2  # Buy + Sell
    trade['net_pnl'] = trade['gross_pnl'] - trade['brokerage']
    trade['pct_change'] = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
    
    save_trades(current_user.id, trades)
    
    logger.info(f"Closed trade for user {current_user.username}: {trade['symbol']} - P&L: ₹{trade['net_pnl']:.2f} ({trade['pct_change']:.2f}%)")
    
    return {"success": True, "message": "Trade closed successfully", "trade": trade}


@router.get("/find_by_message_id")
async def find_trade_by_message_id(
    message_id: int,
    channel_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Find trade by Telegram message ID.
    Used to match reply messages to their original signal trades.
    """
    trades = load_trades(current_user.id)
    
    # Find trade by message ID and channel ID
    matching_trades = [
        t for t in trades
        if t.get('telegram_message_id') == message_id
        and t.get('telegram_channel_id') == channel_id
        and t.get('status') == 'open'  # Only match open trades
    ]
    
    if not matching_trades:
        return {
            "success": False,
            "message": "No open trade found for this message ID",
            "trade": None
        }
    
    # Return most recent trade if multiple matches (shouldn't happen, but handle it)
    trade = matching_trades[-1]  # Last one is most recent
    
    return {
        "success": True,
        "message": "Trade found",
        "trade": trade
    }


class ModifyTradeRequest(BaseModel):
    message_id: int
    channel_id: int
    instruction: str  # "cancel" or "book_profits"


@router.post("/modify_from_reply")
async def modify_trade_from_reply(
    request: ModifyTradeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Modify trade based on Telegram reply message.
    
    Actions:
    - "cancel": Close trade with exit_reason="cancelled" (if open)
    - "book_profits": Exit trade immediately at current LTP
    """
    message_id = request.message_id
    channel_id = request.channel_id
    instruction = request.instruction
    
    trades = load_trades(current_user.id)
    
    # Find trade by message ID
    trade = next((
        t for t in trades
        if t.get('telegram_message_id') == message_id
        and t.get('telegram_channel_id') == channel_id
        and t.get('status') == 'open'
    ), None)
    
    if not trade:
        raise HTTPException(
            status_code=404,
            detail=f"No open trade found for message ID {message_id} in channel {channel_id}"
        )
    
    if instruction == "cancel":
        # Check if this is a live trade (has Zerodha orders)
        is_live = trade.get('is_live', False)
        buy_order_id = trade.get('zerodha_buy_order_id')
        sl_order_id = trade.get('zerodha_sl_order_id')
        target_order_id = trade.get('zerodha_target_order_id')
        
        # Cancel orders on Zerodha if live trade
        if is_live:
            try:
                from webapp.database import SessionLocal, ZerodhaCredential
                from webapp.zerodha_client import get_zerodha_client
                from webapp.encryption import decrypt_api_key, decrypt_access_token
                
                db_session = SessionLocal()
                try:
                    cred = db_session.query(ZerodhaCredential).filter(
                        ZerodhaCredential.user_id == current_user.id
                    ).first()
                    
                    if cred and cred.is_connected:
                        api_key = decrypt_api_key(cred.api_key)
                        access_token = decrypt_access_token(cred.access_token)
                        client = get_zerodha_client(current_user.id, api_key, access_token)
                        
                        # Cancel pending orders
                        cancelled_orders = []
                        for order_id in [buy_order_id, sl_order_id, target_order_id]:
                            if order_id:
                                try:
                                    client.cancel_order(order_id)
                                    cancelled_orders.append(order_id)
                                    logger.info(f"Cancelled Zerodha order {order_id} for trade {trade['id']}")
                                except Exception as e:
                                    logger.warning(f"Could not cancel Zerodha order {order_id}: {e}")
                        
                        trade['notes'] = (trade.get('notes') or '') + f" | Cancelled via Telegram reply. Zerodha orders cancelled: {', '.join(cancelled_orders) if cancelled_orders else 'none'}"
                    else:
                        trade['notes'] = (trade.get('notes') or '') + f" | Cancelled via Telegram reply (Zerodha not connected)"
                finally:
                    db_session.close()
            except Exception as e:
                logger.error(f"Error cancelling Zerodha orders: {e}")
                trade['notes'] = (trade.get('notes') or '') + f" | Cancelled via Telegram reply (Zerodha cancel failed: {str(e)})"
        
        # Close trade as cancelled
        trade['status'] = 'closed'
        trade['exit_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        trade['exit_price'] = trade['entry_price']  # No price change if cancelled before entry
        trade['exit_reason'] = 'cancelled'
        trade['gross_pnl'] = 0.0
        trade['brokerage'] = 0.0  # No brokerage if cancelled before execution
        trade['net_pnl'] = 0.0
        trade['pct_change'] = 0.0
        
        if not trade.get('notes') or 'Cancelled via Telegram reply' not in trade.get('notes', ''):
            trade['notes'] = (trade.get('notes') or '') + f" | Cancelled via Telegram reply"
        
        save_trades(current_user.id, trades)
        logger.info(f"Cancelled trade {trade['id']} for user {current_user.username} via Telegram reply")
        
        return {
            "success": True,
            "message": "Trade cancelled successfully",
            "trade": trade,
            "zerodha_orders_cancelled": is_live and (buy_order_id or sl_order_id or target_order_id)
        }
    
    elif instruction == "book_profits":
        # Check if this is a live trade (has Zerodha orders)
        is_live = trade.get('is_live', False)
        buy_order_id = trade.get('zerodha_buy_order_id')
        
        # For live trades, place SELL order on Zerodha
        if is_live:
            try:
                from webapp.database import SessionLocal, ZerodhaCredential
                from webapp.zerodha_client import get_zerodha_client
                from webapp.encryption import decrypt_api_key, decrypt_access_token
                from webapp.order_manager import (
                    is_option_symbol, get_option_exchange, get_product_type_for_option,
                    get_product_type_for_stock, extract_underlying_from_option_symbol
                )
                from webapp.utils.options import get_option_lot_size
                
                db_session = SessionLocal()
                try:
                    cred = db_session.query(ZerodhaCredential).filter(
                        ZerodhaCredential.user_id == current_user.id
                    ).first()
                    
                    if not cred or not cred.is_connected:
                        raise HTTPException(
                            status_code=400,
                            detail="Zerodha account not connected. Cannot book profits for live trade."
                        )
                    
                    api_key = decrypt_api_key(cred.api_key)
                    access_token = decrypt_access_token(cred.access_token)
                    client = get_zerodha_client(current_user.id, api_key, access_token)
                
                    # Get trade details
                    symbol = trade.get('symbol', '').replace('.NS', '')
                    is_option = trade.get('instrument_type') == 'option'
                    shares = int(trade.get('shares', 1) or 1)
                    
                    # Determine exchange and product
                    if is_option:
                        # Construct option symbol
                        from webapp.api.eod_monitor import construct_nse_option_symbol
                        strike = float(trade.get('option_strike', 0))
                        option_type = trade.get('option_type', 'CE')
                        expiry_month = trade.get('option_expiry_month')
                        
                        if not expiry_month:
                            raise HTTPException(
                                status_code=400,
                                detail="Expiry month not found for option trade"
                            )
                        
                        option_symbol = construct_nse_option_symbol(symbol, strike, option_type, expiry_month)
                        if not option_symbol:
                            raise HTTPException(
                                status_code=400,
                                detail="Could not construct option symbol"
                            )
                        
                        exchange = get_option_exchange(option_symbol)
                        product = get_product_type_for_option()
                        
                        # Get lot size
                        underlying = extract_underlying_from_option_symbol(option_symbol)
                        lot_size = get_option_lot_size(underlying) if underlying else 1
                        quantity = shares * lot_size
                    else:
                        option_symbol = symbol
                        exchange = trade.get('exchange', 'NSE')
                        product = get_product_type_for_stock()
                        quantity = shares
                    
                    # Place SELL order (exit position)
                    try:
                        exit_order = client.place_order(
                            symbol=option_symbol,
                            exchange=exchange,
                            transaction_type="SELL",
                            quantity=quantity,
                            order_type="MARKET",  # Market order for immediate exit
                            product=product,
                            validity="DAY"
                        )
                        
                        exit_order_id = exit_order.get('order_id')
                        trade['zerodha_exit_order_id'] = exit_order_id
                        trade['notes'] = (trade.get('notes') or '') + f" | Booked profits via Telegram reply. Exit order: {exit_order_id}"
                        
                        logger.info(f"Placed exit order {exit_order_id} on Zerodha for trade {trade['id']}")
                        
                    except Exception as e:
                        logger.error(f"Error placing exit order on Zerodha: {e}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to place exit order on Zerodha: {str(e)}"
                        )
                finally:
                    db_session.close()
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error booking profits on Zerodha: {e}")
                # Fall back to paper trade exit
                is_live = False
        
        # Get current LTP for P&L calculation
        is_option = trade.get('instrument_type') == 'option'
        
        if is_option:
            # Get current LTP for option
            try:
                symbol = trade.get('symbol', '').replace('.NS', '')
                strike = float(trade.get('option_strike', 0))
                option_type = trade.get('option_type', 'CE')
                expiry_month = trade.get('option_expiry_month')
                
                result = get_option_ltp(symbol, strike, option_type, expiry_month)
                # Handle return value (always returns 4 values: ltp, resolved_expiry, today_high, today_low)
                if len(result) == 2:
                    current_ltp, _ = result
                else:
                    current_ltp, _, _, _ = result
                
                if current_ltp is None:
                    # Fallback to entry price if LTP unavailable
                    current_ltp = trade['entry_price']
                    logger.warning(f"Could not fetch LTP for {symbol} {strike} {option_type}, using entry price")
            except Exception as e:
                logger.error(f"Error fetching option LTP: {e}")
                current_ltp = trade['entry_price']  # Fallback
        else:
            # For equity, try to get from Zerodha if live, otherwise use entry price
            if is_live:
                try:
                    quotes = client.get_quote([f"{exchange}:{symbol}"])
                    quote_data = quotes.get(f"{exchange}:{symbol}", {})
                    ohlc = quote_data.get('ohlc', {})
                    current_ltp = ohlc.get('last_price') or quote_data.get('last_price') or trade['entry_price']
                except:
                    current_ltp = trade['entry_price']
            else:
                current_ltp = trade['entry_price']
                logger.warning("Book profits for equity not fully implemented, using entry price")
        
        # Close trade at current price
        exit_price = current_ltp
        entry_price = float(trade['entry_price'])
        shares = int(trade.get('shares', 1) or 1)
        
        # Calculate P&L - account for lot_size for options
        if is_option:
            lot_size = trade.get('lot_size')
            if not lot_size or lot_size == 1:
                try:
                    lot_size = get_option_lot_size(trade.get('symbol', '').replace('.NS', ''))
                except Exception:
                    lot_size = 1
            effective_qty = shares * int(lot_size)
        else:
            effective_qty = shares
        
        trade['status'] = 'closed'
        trade['exit_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        trade['exit_price'] = exit_price
        trade['exit_reason'] = 'book_profits'
        trade['gross_pnl'] = (exit_price - entry_price) * effective_qty
        trade['brokerage'] = BROKERAGE_PER_TRADE * 2  # Buy + Sell
        trade['net_pnl'] = trade['gross_pnl'] - trade['brokerage']
        trade['pct_change'] = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        
        if not trade.get('notes') or 'Booked profits via Telegram reply' not in trade.get('notes', ''):
            trade['notes'] = (trade.get('notes') or '') + f" | Booked profits via Telegram reply"
        
        save_trades(current_user.id, trades)
        logger.info(
            f"Booked profits for trade {trade['id']} ({trade['symbol']}) "
            f"for user {current_user.username} via Telegram reply. "
            f"Exit: ₹{exit_price:.2f}, P&L: ₹{trade['net_pnl']:.2f}"
        )
        
        return {
            "success": True,
            "message": "Profits booked successfully",
            "trade": trade,
            "zerodha_exit_placed": is_live
        }
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown instruction: {instruction}. Must be 'cancel' or 'book_profits'"
        )


@router.delete("/delete/{trade_id}")
async def delete_trade(trade_id: str, current_user: User = Depends(get_current_user)):
    """Delete a paper trade for current user"""
    trades = load_trades(current_user.id)
    
    trade = next((t for t in trades if t['id'] == trade_id), None)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    trades = [t for t in trades if t['id'] != trade_id]
    save_trades(current_user.id, trades)
    
    logger.info(f"Deleted trade for user {current_user.username}: {trade_id}")
    
    return {"success": True, "message": "Trade deleted successfully"}


@router.delete("/clear-all")
async def clear_all_trades():
    """Clear all paper trades (use with caution!)"""
    save_trades([])
    logger.warning("Cleared all paper trades")
    return {"success": True, "message": "All trades cleared"}


@router.get("/{trade_id}")
async def get_trade(trade_id: str):
    """Get a specific trade by ID"""
    trades = load_trades()
    trade = next((t for t in trades if t['id'] == trade_id), None)
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    return {"success": True, "trade": trade}

