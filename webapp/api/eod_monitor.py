"""
EOD Monitor API
Endpoints for running end-of-day trade checks and viewing results
**NOW WITH TRADE HEALTH MONITORING!**
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import yfinance as yf
import subprocess
import logging

# Add parent directory to path for src imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from webapp.api.paper_trading import load_trades
from webapp.api.auth_api import get_current_user
from webapp.database import User

logger = logging.getLogger(__name__)

# Import trade health monitor
try:
    from trade_health_monitor import TradeHealthMonitor
    HEALTH_CHECK_ENABLED = True
except ImportError:
    logger.warning("Trade health monitor not available")
    HEALTH_CHECK_ENABLED = False

router = APIRouter()

DATA_DIR = Path("webapp/data")
EOD_LOG_FILE = DATA_DIR / "eod_monitor_log.csv"


def fetch_today_ohlc(symbol):
    """Fetch today's OHLC data for a symbol"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1d")
        
        if hist.empty:
            return None
        
        latest = hist.iloc[-1]
        
        return {
            'date': hist.index[-1].strftime('%Y-%m-%d'),
            'open': float(latest['Open']),
            'high': float(latest['High']),
            'low': float(latest['Low']),
            'close': float(latest['Close']),
            'volume': int(latest['Volume'])
        }
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None


def check_trade_status(trade, ohlc, brokerage_per_trade=20):
    """Check if trade hit SL or Target"""
    entry_price = trade['entry_price']
    stop_loss = trade['stop_loss']
    target = trade['target']
    shares = trade['shares']
    
    today_high = ohlc['high']
    today_low = ohlc['low']
    current_price = ohlc['close']
    
    # Check target hit
    if today_high >= target:
        gross_pnl = (target - entry_price) * shares
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        return {
            'status': 'TARGET_HIT',
            'exit_price': target,
            'exit_reason': 'target',
            'current_price': current_price,
            'pnl_pct': ((target - entry_price) / entry_price) * 100,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl
        }
    
    # Check stop loss hit
    if today_low <= stop_loss:
        gross_pnl = (stop_loss - entry_price) * shares
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        return {
            'status': 'STOP_LOSS_HIT',
            'exit_price': stop_loss,
            'exit_reason': 'stop_loss',
            'current_price': current_price,
            'pnl_pct': ((stop_loss - entry_price) / entry_price) * 100,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl
        }
    
    # Check time stop (120 days)
    entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d %H:%M:%S')
    days_held = (datetime.now() - entry_date).days
    
    if days_held >= 120:
        gross_pnl = (current_price - entry_price) * shares
        net_pnl = gross_pnl - (brokerage_per_trade * 2)
        return {
            'status': 'TIME_STOP',
            'exit_price': current_price,
            'exit_reason': 'time_stop',
            'current_price': current_price,
            'pnl_pct': ((current_price - entry_price) / entry_price) * 100,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'days_held': days_held
        }
    
    # Still open
    unrealized_pnl = (current_price - entry_price) * shares
    return {
        'status': 'OPEN',
        'current_price': current_price,
        'pnl_pct': ((current_price - entry_price) / entry_price) * 100,
        'unrealized_pnl': unrealized_pnl,
        'days_held': days_held
    }


@router.get("/check", summary="Run EOD check on all open trades")
async def run_eod_check(current_user: User = Depends(get_current_user)):
    """
    Check all open trades for SL/Target hits
    **NEW: Also checks trade health (momentum, volume, trend)**
    Returns detailed status for each trade
    """
    try:
        # Load user-specific trades
        all_trades = load_trades(current_user.id)
        
        # Filter open trades
        open_trades = [t for t in all_trades if t['status'] == 'open']
        
        if not open_trades:
            return JSONResponse({
                'success': True,
                'message': 'No open trades to check',
                'trades_checked': 0,
                'trades_to_close': [],
                'trades_still_open': [],
                'health_warnings': []
            })
        
        # Initialize health monitor
        health_monitor = None
        if HEALTH_CHECK_ENABLED:
            health_monitor = TradeHealthMonitor()
        
        trades_to_close = []
        trades_still_open = []
        health_warnings = []  # Tracks with WARNING or CRITICAL health
        
        # Check each trade
        for trade in open_trades:
            symbol = trade['symbol']
            
            # Fetch OHLC
            ohlc = fetch_today_ohlc(symbol)
            
            if not ohlc:
                logger.warning(f"Could not fetch data for {symbol}")
                continue
            
            # Check status
            status = check_trade_status(trade, ohlc)
            
            # **NEW: Check trade health if still open**
            health_info = None
            if health_monitor and status['status'] == 'OPEN':
                try:
                    health_info = health_monitor.check_trade_health(trade)
                except Exception as e:
                    logger.warning(f"Health check failed for {symbol}: {e}")
            
            # Add OHLC, status, and health to trade
            trade_result = {
                **trade,
                'ohlc': ohlc,
                'check_status': status,
                'health_info': health_info  # **NEW**
            }
            
            if status['status'] in ['TARGET_HIT', 'STOP_LOSS_HIT', 'TIME_STOP']:
                trades_to_close.append(trade_result)
            else:
                trades_still_open.append(trade_result)
                
                # **NEW: Track health warnings**
                if health_info and health_info.get('status') in ['WARNING', 'CRITICAL']:
                    health_warnings.append(trade_result)
        
        # Log this check
        log_eod_check(trades_to_close, trades_still_open)
        
        return JSONResponse({
            'success': True,
            'message': f'Checked {len(open_trades)} open trades',
            'timestamp': datetime.now().isoformat(),
            'trades_checked': len(open_trades),
            'trades_to_close': trades_to_close,
            'trades_still_open': trades_still_open,
            'health_warnings': health_warnings,  # **NEW**
            'summary': {
                'total_checked': len(open_trades),
                'need_closing': len(trades_to_close),
                'still_open': len(trades_still_open),
                'targets_hit': len([t for t in trades_to_close if t['check_status']['status'] == 'TARGET_HIT']),
                'stop_losses_hit': len([t for t in trades_to_close if t['check_status']['status'] == 'STOP_LOSS_HIT']),
                'time_stops': len([t for t in trades_to_close if t['check_status']['status'] == 'TIME_STOP']),
                'health_warnings': len(health_warnings),  # **NEW**
                'health_critical': len([t for t in health_warnings if t.get('health_info', {}).get('status') == 'CRITICAL'])  # **NEW**
            }
        })
    
    except Exception as e:
        logger.error(f"Error running EOD check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", summary="Get EOD check history")
async def get_eod_history(limit: int = 100):
    """
    Get historical EOD check logs
    """
    try:
        if not EOD_LOG_FILE.exists():
            return JSONResponse({
                'success': True,
                'history': [],
                'message': 'No history available yet'
            })
        
        # Read log file
        history = []
        with open(EOD_LOG_FILE, 'r') as f:
            lines = f.readlines()
            
            # Skip header
            if len(lines) > 1:
                # Get last N lines
                for line in lines[-limit:]:
                    parts = line.strip().split(',')
                    if len(parts) >= 12:
                        history.append({
                            'date': parts[0],
                            'time': parts[1],
                            'symbol': parts[2],
                            'entry_price': float(parts[3]),
                            'current_price': float(parts[4]),
                            'high': float(parts[5]),
                            'low': float(parts[6]),
                            'stop_loss': float(parts[7]),
                            'target': float(parts[8]),
                            'status': parts[9],
                            'days_held': int(parts[10]),
                            'pnl_pct': float(parts[11])
                        })
        
        return JSONResponse({
            'success': True,
            'history': list(reversed(history)),  # Most recent first
            'count': len(history)
        })
    
    except Exception as e:
        logger.error(f"Error reading EOD history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def log_eod_check(trades_to_close, trades_still_open):
    """Log EOD check to CSV"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create log file with headers if it doesn't exist
        if not EOD_LOG_FILE.exists():
            with open(EOD_LOG_FILE, 'w') as f:
                f.write("date,time,symbol,entry_price,current_price,high,low,stop_loss,target,status,days_held,pnl_pct\n")
        
        # Append checks
        with open(EOD_LOG_FILE, 'a') as f:
            timestamp = datetime.now()
            date_str = timestamp.strftime('%Y-%m-%d')
            time_str = timestamp.strftime('%H:%M:%S')
            
            # Log trades to close
            for trade in trades_to_close:
                status = trade['check_status']
                ohlc = trade['ohlc']
                f.write(f"{date_str},{time_str},")
                f.write(f"{trade['symbol']},")
                f.write(f"{trade['entry_price']:.2f},")
                f.write(f"{ohlc['close']:.2f},")
                f.write(f"{ohlc['high']:.2f},")
                f.write(f"{ohlc['low']:.2f},")
                f.write(f"{trade['stop_loss']:.2f},")
                f.write(f"{trade['target']:.2f},")
                f.write(f"{status['status']},")
                f.write(f"{status.get('days_held', 0)},")
                f.write(f"{status['pnl_pct']:.2f}\n")
            
            # Log open trades
            for trade in trades_still_open:
                status = trade['check_status']
                ohlc = trade['ohlc']
                f.write(f"{date_str},{time_str},")
                f.write(f"{trade['symbol']},")
                f.write(f"{trade['entry_price']:.2f},")
                f.write(f"{ohlc['close']:.2f},")
                f.write(f"{ohlc['high']:.2f},")
                f.write(f"{ohlc['low']:.2f},")
                f.write(f"{trade['stop_loss']:.2f},")
                f.write(f"{trade['target']:.2f},")
                f.write(f"OPEN,")
                f.write(f"{status['days_held']},")
                f.write(f"{status['pnl_pct']:.2f}\n")
    
    except Exception as e:
        logger.error(f"Error logging EOD check: {e}")


@router.post("/auto-close", summary="Auto-close trades that hit SL/Target")
async def auto_close_trades(current_user: User = Depends(get_current_user), auth_token: str = None):
    """
    Automatically close trades that hit their SL or Target
    For live trades: Places SELL orders on Zerodha (requires auth_token)
    For paper trades: Closes in webapp database
    """
    try:
        # Run EOD check first (passing current_user)
        check_result = await run_eod_check(current_user)
        
        if not check_result:
            raise HTTPException(status_code=500, detail="Failed to run EOD check")
        
        result_data = json.loads(check_result.body.decode())
        
        if not result_data['success']:
            raise HTTPException(status_code=500, detail="EOD check failed")
        
        trades_to_close = result_data['trades_to_close']
        
        if not trades_to_close:
            return JSONResponse({
                'success': True,
                'message': 'No trades need closing',
                'closed_count': 0,
                'live_closed': 0,
                'paper_closed': 0
            })
        
        # Separate live and paper trades
        live_trades = [t for t in trades_to_close if t.get('is_live', False)]
        paper_trades = [t for t in trades_to_close if not t.get('is_live', False)]
        
        closed_count = 0
        live_closed_count = 0
        paper_closed_count = 0
        closed_trades = []
        failed_trades = []
        
        # Handle live trades (place SELL orders on Zerodha)
        if live_trades:
            if not auth_token:
                logger.warning("Live trades found but no auth token provided")
                for trade in live_trades:
                    failed_trades.append({
                        'symbol': trade['symbol'],
                        'reason': 'No auth token - cannot place Zerodha order'
                    })
            else:
                # Import order placement function
                import requests
                
                for trade_result in live_trades:
                    trade = trade_result
                    status = trade['check_status']
                    
                    try:
                        # Place SELL order on Zerodha
                        symbol = trade['symbol'].replace('.NS', '')
                        
                        order_data = {
                            'symbol': symbol,
                            'exchange': 'NSE',
                            'transaction_type': 'SELL',
                            'quantity': trade['shares'],
                            'order_type': 'MARKET',
                            'product': 'CNC',
                            'validity': 'DAY',
                            'notes': f"EOD Auto-exit: {status['exit_reason']}"
                        }
                        
                        # Call orders API
                        response = requests.post(
                            'http://localhost:8000/api/orders/place',
                            json=order_data,
                            headers={'Authorization': f'Bearer {auth_token}'},
                            timeout=15
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get('success'):
                                # Also close in webapp for tracking
                                from webapp.api.paper_trading import close_trade
                                await close_trade(
                                    trade['id'],
                                    exit_price=status['exit_price'],
                                    exit_reason=status['exit_reason'],
                                    notes=f"Zerodha Order: {result.get('zerodha_order_id')}. Auto-closed by EOD Monitor"
                                )
                                
                                closed_count += 1
                                live_closed_count += 1
                                closed_trades.append({
                                    'type': 'LIVE',
                                    'symbol': trade['symbol'],
                                    'exit_price': status['exit_price'],
                                    'pnl': status['net_pnl'],
                                    'reason': status['exit_reason'],
                                    'zerodha_order_id': result.get('zerodha_order_id')
                                })
                            else:
                                failed_trades.append({
                                    'symbol': trade['symbol'],
                                    'reason': result.get('message', 'Unknown error')
                                })
                        else:
                            failed_trades.append({
                                'symbol': trade['symbol'],
                                'reason': f'HTTP {response.status_code}'
                            })
                    
                    except Exception as e:
                        logger.error(f"Error closing live trade {trade['symbol']}: {e}")
                        failed_trades.append({
                            'symbol': trade['symbol'],
                            'reason': str(e)
                        })
        
        # Handle paper trades (close in webapp only)
        for trade_result in paper_trades:
            trade = trade_result
            status = trade['check_status']
            
            try:
                # Call the close endpoint from paper_trading
                from webapp.api.paper_trading import close_trade
                
                result = await close_trade(
                    trade['id'],
                    exit_price=status['exit_price'],
                    exit_reason=status['exit_reason'],
                    notes=f"Auto-closed by EOD Monitor: {status['status']}"
                )
                
                if result.status_code == 200:
                    closed_count += 1
                    paper_closed_count += 1
                    closed_trades.append({
                        'type': 'PAPER',
                        'symbol': trade['symbol'],
                        'exit_price': status['exit_price'],
                        'pnl': status['net_pnl'],
                        'reason': status['exit_reason']
                    })
                else:
                    failed_trades.append({
                        'symbol': trade['symbol'],
                        'reason': 'Failed to close in webapp'
                    })
            
            except Exception as e:
                logger.error(f"Error auto-closing {trade['symbol']}: {e}")
                failed_trades.append({
                    'symbol': trade['symbol'],
                    'reason': str(e)
                })
        
        return JSONResponse({
            'success': True,
            'message': f'Auto-closed {closed_count} trades (Live: {live_closed_count}, Paper: {paper_closed_count})',
            'closed_count': closed_count,
            'live_closed': live_closed_count,
            'paper_closed': paper_closed_count,
            'closed_trades': closed_trades,
            'failed_trades': failed_trades
        })
    
    except Exception as e:
        logger.error(f"Error in auto-close: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

