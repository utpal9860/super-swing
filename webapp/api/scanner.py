"""
Scanner API
Integrates with weekly_trade_scanner.py for signal detection
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import sys
from pathlib import Path
import logging
import subprocess
import pandas as pd
from datetime import datetime


class AIScanRequest(BaseModel):
    strategy: str
    api_key: str
    market_cap: str = "Large Cap"
    sector: Optional[str] = None
    max_stocks: int = 10
    model: str = "gemini-1.5-flash"


class AIFnoScanRequest(BaseModel):
    api_key: str
    trade_type: str = "call_options"  # futures, call_options, put_options, mixed
    index_or_stock: str = "NIFTY"  # NIFTY, BANKNIFTY, or Stock
    strategy: str = "intraday"  # intraday, swing, hedging
    risk_appetite: str = "medium"  # low, medium, high
    max_trades: int = 5
    model: str = "gemini-1.5-flash"


class AIWatchlistRequest(BaseModel):
    api_key: str
    symbols: List[str]  # List of stock symbols
    strategy: str = "swing"  # swing, intraday, long_term
    model: str = "gemini-1.5-flash"

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import OUTPUT_DIR, RAW_DATA_DIR
from src.scanner.data_fetcher import fetch_weekly, load_cached
from src.scanner.indicators import supertrend, calculate_momentum, calculate_sma, calculate_rsi

logger = logging.getLogger(__name__)

router = APIRouter()

# Scanner status
scanner_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_stock": "",
    "signals_found": 0,
    "last_scan": None
}


class ScanRequest(BaseModel):
    """Scanner request model"""
    strategy: str = "momentum_btst"  # momentum_btst, swing_supertrend, mean_reversion
    top_n: int = 50
    lookback_days: int = 14
    capital: float = 100000


@router.get("/status")
async def get_scanner_status():
    """Get current scanner status"""
    return {"success": True, "status": scanner_status}


@router.get("/latest-signals")
async def get_latest_signals(strategy: str = "all", capital: float = 100000):
    """Get latest scanner signals for a specific strategy or all"""
    try:
        # Import position sizing utilities
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from utils.position_sizing import calculate_position_size, calculate_risk_reward
        
        # Define file patterns for each strategy
        patterns = {
            "momentum_btst": "btst_opportunities_*.csv",
            "improved_btst": "improved_btst_*.csv",
            "swing_supertrend": "swing_opportunities_*.csv",
            "mean_reversion": "reversion_opportunities_*.csv",
            "pullback_entry": "pullback_opportunities_*.csv",
            "swing_breakout_india": "swing_breakout_india_opportunities_*.csv",
            "all": "weekly_trades_*.csv"
        }
        
        pattern = patterns.get(strategy, patterns["all"])
        
        # Find the most recent signals file
        latest_file = None
        latest_time = None
        
        project_root = Path(__file__).parent.parent.parent
        
        # Check for strategy-specific files in project root
        for f in project_root.glob(pattern):
            if latest_time is None or f.stat().st_mtime > latest_time:
                latest_time = f.stat().st_mtime
                latest_file = f
        
        # Fallback to OUTPUT_DIR for weekly trades
        if not latest_file:
            for f in OUTPUT_DIR.glob(pattern):
                if latest_time is None or f.stat().st_mtime > latest_time:
                    latest_time = f.stat().st_mtime
                    latest_file = f
        
        if not latest_file or not latest_file.exists():
            return {"success": True, "signals": [], "count": 0, "message": "No signals found. Run a scan first.", "strategy": strategy}
        
        # Read the signals
        df = pd.read_csv(latest_file)
        signals = df.to_dict('records')
        
        # Add strategy field if not present (infer from filename or use parameter)
        detected_strategy = strategy
        if strategy == "all":
            # Try to detect strategy from filename
            filename = latest_file.name.lower()
            if "btst" in filename:
                detected_strategy = "momentum_btst"
            elif "swing" in filename:
                detected_strategy = "swing_supertrend"
            elif "reversion" in filename:
                detected_strategy = "mean_reversion"
            elif "pullback" in filename:
                detected_strategy = "pullback_entry"
        
        # Enhance each signal with detailed position sizing
        for signal in signals:
            # Add strategy field if not present (infer from filename or use parameter)
            # Handle both 'strategy' and 'strategy_name' fields
            if 'strategy' not in signal or not signal['strategy']:
                if 'strategy_name' in signal and signal['strategy_name']:
                    signal['strategy'] = signal['strategy_name']
                else:
                    signal['strategy'] = detected_strategy
            
            entry = signal.get('entry_price', signal.get('close', 0))
            sl = signal.get('stop_loss', 0)
            target = signal.get('target_1', signal.get('target', 0))
            
            # Calculate target if missing (use 2:1 R:R ratio)
            if entry > 0 and sl > 0 and (not target or target <= 0 or target <= entry):
                risk = entry - sl
                target = entry + (risk * 2.0)  # 2:1 reward:risk
                signal['target'] = target
                signal['target_calculated'] = True
                logger.info(f"Calculated target for {signal.get('symbol', 'unknown')}: {target:.2f} (2:1 R:R)")
            
            if entry > 0 and sl > 0 and target > 0:
                # Calculate proper position sizing with risk management
                pos_size = calculate_position_size(
                    capital=capital,
                    risk_pct=2.0,  # Risk 2% per trade
                    entry_price=entry,
                    stop_loss=sl
                )
                
                if pos_size:
                    # Update signal with position sizing details
                    signal['shares'] = pos_size['shares']
                    signal['position_value'] = pos_size['position_value']
                    signal['risk_amount'] = pos_size['risk_amount']
                    signal['risk_per_share'] = pos_size['risk_per_share']
                    signal['capital_allocation_pct'] = pos_size['capital_allocation_pct']
                    signal['actual_risk_pct'] = pos_size['actual_risk_pct']
                
                # Calculate R:R ratio
                rr = calculate_risk_reward(entry, sl, target)
                if rr:
                    signal['risk_pct'] = rr['risk_pct']
                    signal['reward_pct'] = rr['reward_pct']
                    signal['risk_reward_ratio'] = rr['risk_reward_ratio']
                    signal['risk_amount_per_share'] = rr['risk_amount']
                    signal['reward_amount_per_share'] = rr['reward_amount']
        
        # Add scan date
        scan_date = datetime.fromtimestamp(latest_time).strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            "success": True,
            "signals": signals,
            "count": len(signals),
            "scan_date": scan_date,
            "file": str(latest_file.name),
            "strategy": strategy,
            "capital_used": capital
        }
    
    except Exception as e:
        logger.error(f"Error reading signals: {e}")
        return {"success": False, "error": str(e), "signals": [], "count": 0, "strategy": strategy}


@router.post("/run")
async def run_scanner(request: ScanRequest, background_tasks: BackgroundTasks):
    """Run the strategy-based scanner"""
    if scanner_status["is_running"]:
        raise HTTPException(status_code=400, detail="Scanner is already running")
    
    # Run scanner in background
    background_tasks.add_task(
        execute_scanner,
        request.strategy,
        request.top_n,
        request.lookback_days,
        request.capital
    )
    
    return {
        "success": True,
        "message": f"{request.strategy.replace('_', ' ').title()} scanner started. Check /api/scanner/status for progress.",
        "strategy": request.strategy
    }


async def execute_scanner(strategy: str, top_n: int, lookback_days: int, capital: float):
    """Execute the strategy-specific scanner script"""
    global scanner_status
    
    scanner_status["is_running"] = True
    scanner_status["progress"] = 0
    scanner_status["signals_found"] = 0
    scanner_status["current_stock"] = f"Starting {strategy} scan..."
    
    try:
        # Handle strategies programmatically (no external scripts needed)
        programmatic_strategies = {
            "pullback_entry": "PullbackEntryStrategy",
            "momentum_btst": "MomentumBTSTStrategy",
            "improved_btst": "ImprovedBTSTStrategy",
            "swing_supertrend": "SwingSuperTrendStrategy",
            "mean_reversion": "MeanReversionStrategy",
            "swing_breakout_india": "SwingBreakoutIndiaStrategy"
        }
        
        if strategy in programmatic_strategies:
            await execute_programmatic_scanner(strategy, programmatic_strategies[strategy], top_n, capital)
            return
        
        # Map remaining strategies to scanner scripts (legacy)
        scanner_scripts = {
            "all": "weekly_trade_scanner.py"  # Original scanner
        }
        
        script = scanner_scripts.get(strategy, "weekly_trade_scanner.py")
        
        # Run the appropriate scanner script
        cmd = ["python", script]
        
        # Add arguments if it's the weekly scanner
        if strategy == "all":
            cmd.extend([
                "--top-n", str(top_n),
                "--lookback-days", str(lookback_days),
                "--capital", str(capital)
            ])
        
        logger.info(f"Running {strategy} scanner: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=Path(__file__).parent.parent.parent
        )
        
        if result.returncode == 0:
            # Parse output to get number of signals
            output = result.stdout
            
            # Try to find signal count in various formats
            for line in output.split('\n'):
                if "Found" in line and "opportunities" in line.lower():
                    try:
                        count = int(''.join(filter(str.isdigit, line.split("Found")[1].split("opportunities")[0])))
                        scanner_status["signals_found"] = count
                        break
                    except:
                        pass
                elif "Total Signals:" in line:
                    try:
                        count = line.split(':')[-1].strip()
                        scanner_status["signals_found"] = int(count)
                        break
                    except:
                        pass
            
            scanner_status["last_scan"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"{strategy} scanner completed successfully. Found {scanner_status['signals_found']} signals")
        else:
            logger.error(f"Scanner failed: {result.stderr}")
            scanner_status["current_stock"] = f"Error: {result.stderr[:100]}"
    
    except Exception as e:
        logger.error(f"Error running scanner: {e}")
        scanner_status["current_stock"] = f"Error: {str(e)}"
    
    finally:
        scanner_status["is_running"] = False
        scanner_status["progress"] = 100


async def execute_programmatic_scanner(strategy_id: str, strategy_class_name: str, top_n: int, capital: float):
    """Execute a programmatic strategy scanner (using BaseStrategy classes)"""
    global scanner_status
    
    try:
        scanner_status["progress"] = 1
        scanner_status["current_stock"] = f"Loading {strategy_id} strategy..."
        
        # Import the strategy class dynamically
        if strategy_id == "pullback_entry":
            from strategies.pullback_entry import PullbackEntryStrategy
            strategy = PullbackEntryStrategy()
        elif strategy_id == "momentum_btst":
            from strategies.momentum_btst import MomentumBTSTStrategy
            strategy = MomentumBTSTStrategy()
        elif strategy_id == "improved_btst":
            from strategies.improved_btst import ImprovedBTSTStrategy
            strategy = ImprovedBTSTStrategy()
        elif strategy_id == "swing_supertrend":
            from strategies.swing_supertrend import SwingSuperTrendStrategy
            strategy = SwingSuperTrendStrategy()
        elif strategy_id == "mean_reversion":
            from strategies.mean_reversion import MeanReversionStrategy
            strategy = MeanReversionStrategy()
        elif strategy_id == "swing_breakout_india":
            from strategies.swing_breakout_india import SwingBreakoutIndiaStrategy
            strategy = SwingBreakoutIndiaStrategy()
        else:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        
        # Load quality watchlist
        scanner_status["progress"] = 5
        scanner_status["current_stock"] = "Loading quality watchlist..."
        
        project_root = Path(__file__).parent.parent.parent
        watchlist_path = project_root / "data" / "output" / "quality_watchlist.csv"
        
        if not watchlist_path.exists():
            raise FileNotFoundError(f"Quality watchlist not found at {watchlist_path}")
        
        import pandas as pd
        df = pd.read_csv(watchlist_path)
        symbols = df['symbol'].tolist()
        
        # Add .NS suffix if needed
        symbols = [s if s.endswith('.NS') else f"{s}.NS" for s in symbols]
        
        # Limit to top N if specified
        if top_n and top_n > 0:
            symbols = symbols[:top_n]
        
        scanner_status["progress"] = 10
        scanner_status["current_stock"] = f"Scanning {len(symbols)} symbols..."
        
        # Run the strategy scan (silent mode for API)
        signals = strategy.scan(symbols, capital=capital, silent=True)
        
        scanner_status["progress"] = 90
        scanner_status["signals_found"] = len(signals)
        
        # Save signals to CSV
        if signals:
            output_file = f"{strategy_id}_opportunities_{datetime.now().strftime('%Y-%m-%d')}.csv"
            output_dir = project_root / "data" / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / output_file
            strategy.save_signals(str(output_path))
        
        scanner_status["progress"] = 100
        scanner_status["current_stock"] = f"Scan complete! Found {len(signals)} signals"
        scanner_status["last_scan"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        scanner_status["current_stock"] = f"Error: {str(e)}"
        raise


async def execute_pullback_scanner(top_n: int, capital: float):
    """Execute Pullback Entry scanner programmatically"""
    global scanner_status
    
    try:
        # Import required modules
        from strategies.pullback_entry import PullbackEntryStrategy
        import pandas as pd
        
        # Try to find a watchlist file (same locations as other strategies)
        project_root = Path(__file__).parent.parent.parent
        possible_watchlists = [
            project_root / "data" / "output" / "quality_watchlist.csv",  # Same as other strategies
            project_root / "quality_watchlist.csv",
            project_root / "Ticker_List_NSE_India.csv",
            project_root / "examples" / "Ticker_List_NSE_India.csv"
        ]
        
        watchlist_path = None
        for path in possible_watchlists:
            if path.exists():
                watchlist_path = path
                break
        
        if not watchlist_path:
            scanner_status["current_stock"] = "Error: No watchlist found"
            scanner_status["is_running"] = False
            return
        
        # Load symbols
        df = pd.read_csv(watchlist_path)
        symbol_col = None
        for col in ['symbol', 'Symbol', 'SYMBOL', 'ticker', 'Ticker']:
            if col in df.columns:
                symbol_col = col
                break
        
        if symbol_col is None:
            symbols = df.iloc[:, 0].tolist()
        else:
            symbols = df[symbol_col].tolist()
        
        # Add .NS suffix if needed
        symbols = [s if s.endswith('.NS') else f"{s}.NS" for s in symbols]
        
        # Limit to top_n if specified
        if top_n and top_n > 0:
            symbols = symbols[:top_n]
        
        scanner_status["total"] = len(symbols)
        scanner_status["progress"] = 1  # Start at 1% to show activity
        scanner_status["current_stock"] = f"Initializing scanner for {len(symbols)} stocks..."
        
        # Initialize strategy
        strategy = PullbackEntryStrategy()
        
        # Scan symbols
        signals = []
        for i, symbol in enumerate(symbols, 1):
            # Update progress (ensure minimum 1% visible progress)
            scanner_status["progress"] = max(1, int((i / len(symbols)) * 100))
            scanner_status["current_stock"] = f"[{i}/{len(symbols)}] {symbol}"
            
            try:
                df_data = strategy.fetch_data(symbol, period="6mo", interval="1d")
                
                if df_data is None or len(df_data) < 50:
                    continue
                
                if strategy.validate_signal(df_data):
                    signal = strategy._create_signal(df_data, symbol, capital)
                    if signal:
                        signals.append(signal)
                        scanner_status["signals_found"] = len(signals)
            
            except Exception as e:
                # Silent error handling like other scanners
                continue
        
        # Save results
        if signals:
            output_file = Path(__file__).parent.parent.parent / f"pullback_opportunities_{datetime.now().strftime('%Y-%m-%d')}.csv"
            df_signals = pd.DataFrame([s.to_dict() for s in signals])
            df_signals.to_csv(output_file, index=False)
        
        scanner_status["last_scan"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        scanner_status["current_stock"] = f"Completed: {len(signals)} signals found"
    
    except Exception as e:
        scanner_status["current_stock"] = f"Error: {str(e)}"
    
    finally:
        scanner_status["is_running"] = False
        scanner_status["progress"] = 100


@router.get("/check-signal/{symbol}")
async def check_signal(symbol: str):
    """Check for SuperTrend signal on a specific symbol"""
    try:
        # Load data
        df = load_cached(symbol, RAW_DATA_DIR)
        if df is None or len(df) < 50:
            return {
                "success": False,
                "message": f"Insufficient data for {symbol}"
            }
        
        # Calculate SuperTrend
        df_st = supertrend(df.copy(), atr_period=10, multiplier=3.0)
        
        # Calculate additional indicators
        df_st['MA20'] = calculate_sma(df_st, window=20)
        df_st['MA50'] = calculate_sma(df_st, window=50)
        df_st['RSI'] = calculate_rsi(df_st, window=14)
        df_st['Momentum_4w'] = calculate_momentum(df_st, window=4)
        
        # Get latest values
        latest = df_st.iloc[-1]
        
        signal_info = {
            "symbol": symbol,
            "current_price": float(latest['Close']),
            "supertrend": "UPTREND" if latest['ST_dir'] == 1 else "DOWNTREND",
            "supertrend_value": float(latest['ST']),
            "ma20": float(latest['MA20']),
            "ma50": float(latest['MA50']),
            "rsi": float(latest['RSI']),
            "momentum_4w": float(latest['Momentum_4w']),
            "atr": float(latest['ATR']),
            "date": str(latest['Date'])
        }
        
        # Check for recent buy signal
        has_signal = False
        if len(df_st) >= 2:
            prev_dir = df_st['ST_dir'].iloc[-2]
            curr_dir = df_st['ST_dir'].iloc[-1]
            if prev_dir == -1 and curr_dir == 1:
                has_signal = True
        
        signal_info["has_fresh_signal"] = has_signal
        
        return {
            "success": True,
            "signal": signal_info
        }
    
    except Exception as e:
        logger.error(f"Error checking signal for {symbol}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/ai-scan")
async def ai_stock_scan(request: AIScanRequest):
    """
    AI-powered stock scanner that recommends stocks based on strategy
    
    Args:
        request: AIScanRequest with strategy, api_key, market_cap, sector, max_stocks, model
        
    Returns:
        AI-recommended stocks with analysis
    """
    try:
        from utils.ai_stock_scanner import scan_with_ai
        
        logger.info(f"AI scan requested: {request.strategy}, {request.market_cap}, {request.sector or 'All sectors'}")
        
        result = scan_with_ai(
            api_key=request.api_key,
            strategy=request.strategy,
            market_cap=request.market_cap,
            sector=request.sector,
            max_stocks=request.max_stocks,
            model=request.model
        )
        
        return result
    
    except Exception as e:
        logger.error(f"AI scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-fno-scan")
async def ai_fno_stock_scan(request: AIFnoScanRequest):
    """
    AI-powered F&O scanner that recommends futures and options trades
    
    Args:
        request: AIFnoScanRequest with trade_type, index_or_stock, strategy, risk_appetite, max_trades, model
        
    Returns:
        AI-recommended F&O trades with detailed analysis, Greeks, and data freshness
    """
    try:
        from utils.ai_fno_scanner import scan_fno_with_ai
        
        logger.info(f"F&O AI scan requested: {request.trade_type}, {request.index_or_stock}, {request.strategy}, {request.risk_appetite}")
        
        result = scan_fno_with_ai(
            api_key=request.api_key,
            trade_type=request.trade_type,
            index_or_stock=request.index_or_stock,
            strategy=request.strategy,
            risk_appetite=request.risk_appetite,
            max_trades=request.max_trades,
            model=request.model
        )
        
        return result
    
    except Exception as e:
        logger.error(f"F&O AI scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai-watchlist-analyze")
async def ai_watchlist_analyze(request: AIWatchlistRequest):
    """
    AI-powered analysis of user's custom watchlist
    
    Args:
        request: AIWatchlistRequest with symbols, strategy, model
        
    Returns:
        Detailed AI analysis for each stock in watchlist
    """
    try:
        from utils.ai_watchlist_analyzer import analyze_custom_watchlist
        
        logger.info(f"Custom watchlist analysis requested: {request.symbols}, {request.strategy}")
        
        result = analyze_custom_watchlist(
            api_key=request.api_key,
            symbols=request.symbols,
            strategy=request.strategy,
            model=request.model
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Custom watchlist analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

