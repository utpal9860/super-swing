"""
Strategy Analytics API

Endpoints for strategy performance tracking and comparison.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional
from pydantic import BaseModel
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.performance_tracker import StrategyPerformanceTracker, TradeResult
from webapp.database import get_db, User
from webapp.api.auth_api import get_current_user
from webapp.api.paper_trading import load_trades

router = APIRouter()

# Initialize tracker
tracker = StrategyPerformanceTracker()


class TradeResultRequest(BaseModel):
    """Request model for adding a trade result"""
    trade_id: str
    symbol: str
    strategy: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    exit_reason: str


@router.get("/strategies")
async def get_all_strategies():
    """Get list of all strategies with performance data"""
    try:
        strategies = tracker.get_all_strategies()
        return {
            "success": True,
            "strategies": strategies,
            "count": len(strategies)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/metrics/{strategy}")
async def get_strategy_metrics(strategy: str):
    """Get performance metrics for a specific strategy"""
    try:
        metrics = tracker.calculate_metrics(strategy)
        
        if not metrics:
            return {
                "success": False,
                "error": f"No data found for strategy: {strategy}"
            }
        
        return {
            "success": True,
            "metrics": metrics.to_dict()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/comparison")
async def get_strategy_comparison():
    """Get side-by-side comparison of all strategies"""
    try:
        df = tracker.get_strategy_comparison()
        
        if df.empty:
            return {
                "success": True,
                "strategies": [],
                "message": "No performance data available"
            }
        
        # Convert DataFrame to list of dicts
        strategies = df.to_dict('records')
        
        return {
            "success": True,
            "strategies": strategies,
            "count": len(strategies)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/trades/{strategy}")
async def get_strategy_trades(strategy: str, limit: Optional[int] = 50):
    """Get trades for a specific strategy"""
    try:
        trades = tracker.get_trades_by_strategy(strategy, limit=limit)
        
        return {
            "success": True,
            "strategy": strategy,
            "trades": trades,
            "count": len(trades)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/trades/recent/{days}")
async def get_recent_trades(days: int = 30, strategy: Optional[str] = None):
    """Get recent trades across all or specific strategy"""
    try:
        trades = tracker.get_recent_trades(days=days, strategy=strategy)
        
        return {
            "success": True,
            "days": days,
            "strategy": strategy or "all",
            "trades": trades,
            "count": len(trades)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/trade/add")
async def add_trade_result(trade: TradeResultRequest):
    """Add a completed trade to the performance tracker"""
    try:
        # Calculate P&L
        profit_loss = (trade.exit_price - trade.entry_price) * trade.shares
        profit_loss_pct = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100
        
        # Calculate holding days
        from datetime import datetime
        entry_date = datetime.fromisoformat(trade.entry_date.replace(' ', 'T'))
        exit_date = datetime.fromisoformat(trade.exit_date.replace(' ', 'T'))
        holding_days = (exit_date - entry_date).days
        
        # Create TradeResult object
        trade_result = TradeResult(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            strategy=trade.strategy,
            entry_date=trade.entry_date,
            entry_price=trade.entry_price,
            exit_date=trade.exit_date,
            exit_price=trade.exit_price,
            shares=trade.shares,
            profit_loss=profit_loss,
            profit_loss_pct=profit_loss_pct,
            holding_days=holding_days,
            exit_reason=trade.exit_reason
        )
        
        tracker.add_trade_result(trade_result)
        
        return {
            "success": True,
            "message": f"Trade {trade.trade_id} added to performance tracker",
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/sync-from-paper-trades")
async def sync_from_paper_trades():
    """
    Sync closed trades from paper trading system to performance tracker
    
    This should be called periodically (e.g., EOD) to update performance metrics
    """
    try:
        # Import paper trading module
        from webapp.api.paper_trading import load_trades
        from webapp.database import SessionLocal, User
        
        synced_count = 0
        existing_trade_ids = set(t['trade_id'] for t in tracker.trades)
        
        # Get all users
        db = SessionLocal()
        users = db.query(User).all()
        db.close()
        
        for user in users:
            trades = load_trades(user.id)
            
            # Find closed trades not yet in performance tracker
            for trade in trades:
                if trade['status'] == 'closed' and trade['id'] not in existing_trade_ids:
                    # Add to performance tracker
                    tracker.add_trade_from_dict(trade)
                    synced_count += 1
        
        return {
            "success": True,
            "message": f"Synced {synced_count} closed trades",
            "synced_count": synced_count
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/leaderboard")
async def get_strategy_leaderboard():
    """
    Get strategy leaderboard ranked by multiple criteria
    
    Returns strategies ranked by:
    - Total P&L
    - Win Rate
    - Profit Factor
    - Sharpe Ratio
    """
    try:
        df = tracker.get_strategy_comparison()
        
        if df.empty:
            return {
                "success": True,
                "leaderboard": {},
                "message": "No performance data available"
            }
        
        leaderboard = {
            "by_profit": [],
            "by_win_rate": [],
            "by_profit_factor": [],
            "by_sharpe": []
        }
        
        # Rank by total P&L
        if 'total_profit_loss' in df.columns:
            df_profit = df.sort_values('total_profit_loss', ascending=False)
            leaderboard["by_profit"] = df_profit[['strategy_name', 'total_profit_loss', 'total_trades']].head(10).to_dict('records')
        
        # Rank by win rate (min 10 trades)
        if 'win_rate' in df.columns:
            df_winrate = df[df['total_trades'] >= 10].sort_values('win_rate', ascending=False)
            leaderboard["by_win_rate"] = df_winrate[['strategy_name', 'win_rate', 'total_trades']].head(10).to_dict('records')
        
        # Rank by profit factor (min 10 trades)
        if 'profit_factor' in df.columns:
            df_pf = df[df['total_trades'] >= 10].sort_values('profit_factor', ascending=False)
            leaderboard["by_profit_factor"] = df_pf[['strategy_name', 'profit_factor', 'total_trades']].head(10).to_dict('records')
        
        # Rank by Sharpe ratio (min 10 trades)
        if 'sharpe_ratio' in df.columns:
            df_sharpe = df[(df['total_trades'] >= 10) & (df['sharpe_ratio'].notna())].sort_values('sharpe_ratio', ascending=False)
            leaderboard["by_sharpe"] = df_sharpe[['strategy_name', 'sharpe_ratio', 'total_trades']].head(10).to_dict('records')
        
        return {
            "success": True,
            "leaderboard": leaderboard
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/recent-activity")
async def get_recent_activity(
    days: int = 7,
    current_user: User = Depends(get_current_user)
):
    """
    Get recent trading activity for dashboard
    
    Returns recent trades (open and closed) sorted by entry date
    """
    try:
        from webapp.api.paper_trading import load_trades
        from datetime import datetime, timedelta
        
        trades = load_trades(current_user.id)
        
        # Filter to recent trades (last N days)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_trades = []
        for trade in trades:
            try:
                entry_date = datetime.strptime(trade.get('entry_date', ''), '%Y-%m-%d %H:%M:%S')
                if entry_date >= cutoff_date:
                    recent_trades.append(trade)
            except:
                continue
        
        # Sort by entry date (newest first)
        recent_trades.sort(key=lambda x: x.get('entry_date', ''), reverse=True)
        
        return {
            "success": True,
            "trades": recent_trades[:50],  # Limit to 50 most recent
            "count": len(recent_trades)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/pnl-chart")
async def get_pnl_chart(
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get P&L chart data for dashboard
    
    Returns cumulative P&L over time for Chart.js
    """
    try:
        from webapp.api.paper_trading import load_trades
        from datetime import datetime, timedelta
        
        trades = load_trades(current_user.id)
        
        # Filter to closed trades in last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        
        closed_trades = []
        for trade in trades:
            if trade.get('status') != 'closed':
                continue
            
            try:
                exit_date = datetime.strptime(trade.get('exit_date', ''), '%Y-%m-%d %H:%M:%S')
                if exit_date >= cutoff_date:
                    closed_trades.append(trade)
            except:
                continue
        
        # Sort by exit date
        closed_trades.sort(key=lambda x: x.get('exit_date', ''))
        
        # Calculate cumulative P&L
        cumulative_pnl = 0
        labels = []
        data = []
        
        for trade in closed_trades:
            net_pnl = float(trade.get('net_pnl', 0) or 0)
            cumulative_pnl += net_pnl
            
            exit_date = trade.get('exit_date', '')
            try:
                # Format date for chart
                date_obj = datetime.strptime(exit_date, '%Y-%m-%d %H:%M:%S')
                labels.append(date_obj.strftime('%Y-%m-%d'))
            except:
                labels.append(exit_date.split(' ')[0] if ' ' in exit_date else exit_date)
            
            data.append(round(cumulative_pnl, 2))
        
        return {
            "success": True,
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "Cumulative P&L",
                    "data": data,
                    "borderColor": "rgb(75, 192, 192)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "tension": 0.1
                }]
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
