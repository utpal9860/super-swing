"""
Trade Health Monitoring API
Provides early warning signals for trades losing momentum
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
import sys
from pathlib import Path
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trade_health_monitor import TradeHealthMonitor
from webapp.api.paper_trading import load_trades
from webapp.api.auth_api import get_current_user
from webapp.database import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/check-all")
async def check_all_trades_health(current_user: User = Depends(get_current_user)):
    """
    Check health of all open trades
    Returns health scores and warnings for each trade
    """
    try:
        trades = load_trades(current_user.id)
        open_trades = [t for t in trades if t['status'] == 'open']
        
        if not open_trades:
            return {
                "success": True,
                "trades": [],
                "summary": {
                    "total": 0,
                    "critical": 0,
                    "warning": 0,
                    "healthy": 0
                }
            }
        
        monitor = TradeHealthMonitor()
        results = []
        
        for trade in open_trades:
            try:
                health = monitor.check_trade_health(trade)
                
                result = {
                    'trade_id': trade['id'],
                    'symbol': trade['symbol'],
                    'entry_date': trade['entry_date'],
                    'strategy': trade.get('strategy', 'unknown'),
                    'health_score': health['health_score'],
                    'status': health['status'],
                    'recommendation': health['recommendation'],
                    'warnings': health['warnings'],
                    'signals': health['signals'],
                    'current_price': health.get('current_price'),
                    'pct_change': health.get('pct_change'),
                    'days_held': health.get('days_held'),
                    'last_updated': health.get('last_updated')
                }
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error checking health for {trade['symbol']}: {e}")
                results.append({
                    'trade_id': trade['id'],
                    'symbol': trade['symbol'],
                    'health_score': 5,
                    'status': 'UNKNOWN',
                    'recommendation': 'Unable to check',
                    'warnings': [str(e)],
                    'signals': {}
                })
        
        # Calculate summary
        summary = {
            'total': len(results),
            'critical': sum(1 for r in results if r['status'] == 'CRITICAL'),
            'warning': sum(1 for r in results if r['status'] == 'WARNING'),
            'healthy': sum(1 for r in results if r['status'] == 'HEALTHY')
        }
        
        return {
            "success": True,
            "trades": results,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Error in check_all_trades_health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-one/{trade_id}")
async def check_trade_health(trade_id: str, current_user: User = Depends(get_current_user)):
    """
    Check health of a specific trade
    """
    try:
        trades = load_trades(current_user.id)
        trade = next((t for t in trades if t['id'] == trade_id), None)
        
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        if trade['status'] != 'open':
            return {
                "success": True,
                "message": "Trade is already closed",
                "health_score": None
            }
        
        monitor = TradeHealthMonitor()
        health = monitor.check_trade_health(trade)
        
        return {
            "success": True,
            **health
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in check_trade_health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_health_alerts(current_user: User = Depends(get_current_user)):
    """
    Get only trades with warnings or critical status
    """
    try:
        trades = load_trades(current_user.id)
        open_trades = [t for t in trades if t['status'] == 'open']
        
        if not open_trades:
            return {
                "success": True,
                "alerts": [],
                "count": 0
            }
        
        monitor = TradeHealthMonitor()
        alerts = []
        
        for trade in open_trades:
            try:
                health = monitor.check_trade_health(trade)
                
                # Only include if WARNING or CRITICAL
                if health['status'] in ['WARNING', 'CRITICAL']:
                    alert = {
                        'trade_id': trade['id'],
                        'symbol': trade['symbol'],
                        'entry_date': trade['entry_date'],
                        'health_score': health['health_score'],
                        'status': health['status'],
                        'recommendation': health['recommendation'],
                        'warnings': health['warnings'],
                        'current_price': health.get('current_price'),
                        'pct_change': health.get('pct_change')
                    }
                    alerts.append(alert)
                    
            except Exception as e:
                logger.error(f"Error checking health for {trade['symbol']}: {e}")
        
        # Sort by health score (worst first)
        alerts.sort(key=lambda x: x['health_score'])
        
        return {
            "success": True,
            "alerts": alerts,
            "count": len(alerts)
        }
        
    except Exception as e:
        logger.error(f"Error in get_health_alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

