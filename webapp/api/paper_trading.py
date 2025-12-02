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
            "total_invested": 0,
            "gross_pnl": 0,
            "total_brokerage": 0,
            "net_pnl": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0
        }
    
    closed_trades = [t for t in trades if t['status'] == 'closed']
    open_trades = [t for t in trades if t['status'] == 'open']
    
    # Calculate metrics
    total_invested = sum(t['position_value'] for t in open_trades)
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
    
    # Calculate P&L
    trade['gross_pnl'] = (exit_price - trade['entry_price']) * trade['shares']
    trade['brokerage'] = BROKERAGE_PER_TRADE * 2  # Buy + Sell
    trade['net_pnl'] = trade['gross_pnl'] - trade['brokerage']
    trade['pct_change'] = ((exit_price - trade['entry_price']) / trade['entry_price']) * 100
    
    save_trades(current_user.id, trades)
    
    logger.info(f"Closed trade for user {current_user.username}: {trade['symbol']} - P&L: ₹{trade['net_pnl']:.2f} ({trade['pct_change']:.2f}%)")
    
    return {"success": True, "message": "Trade closed successfully", "trade": trade}


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

