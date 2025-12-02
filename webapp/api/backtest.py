"""
Backtest API

Endpoints for running and managing strategy backtests.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import sys
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.backtest_engine import BacktestEngine, BacktestConfig, BacktestResult

router = APIRouter()

# Store backtest status and results
backtest_status = {
    "is_running": False,
    "progress": 0,
    "current_date": "",
    "strategy": "",
    "message": ""
}

# Cache for completed backtests
backtest_results = {}


class BacktestRequest(BaseModel):
    """Request model for running a backtest"""
    strategy: str
    symbols: List[str]
    start_date: str
    end_date: str
    initial_capital: float = 100000
    risk_per_trade: float = 2.0
    max_positions: int = 5
    brokerage_per_trade: float = 20.0


@router.get("/status")
async def get_backtest_status():
    """Get current backtest status"""
    return {"success": True, "status": backtest_status}


@router.post("/run")
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    Run a backtest for a strategy
    
    Args:
        request: BacktestRequest with configuration
        background_tasks: FastAPI background tasks
    """
    global backtest_status
    
    if backtest_status["is_running"]:
        raise HTTPException(status_code=400, detail="A backtest is already running")
    
    # Validate dates
    try:
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
        
        if end_date <= start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        if end_date > datetime.now():
            raise HTTPException(status_code=400, detail="End date cannot be in the future")
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Run backtest in background
    background_tasks.add_task(
        execute_backtest,
        request.strategy,
        request.symbols,
        request.start_date,
        request.end_date,
        request.initial_capital,
        request.risk_per_trade,
        request.max_positions,
        request.brokerage_per_trade
    )
    
    return {
        "success": True,
        "message": f"Backtest started for {request.strategy}",
        "strategy": request.strategy,
        "period": f"{request.start_date} to {request.end_date}"
    }


async def execute_backtest(
    strategy_name: str,
    symbols: List[str],
    start_date: str,
    end_date: str,
    initial_capital: float,
    risk_per_trade: float,
    max_positions: int,
    brokerage_per_trade: float
):
    """Execute backtest in background (non-blocking)"""
    global backtest_status, backtest_results
    
    try:
        backtest_status["is_running"] = True
        backtest_status["progress"] = 0
        backtest_status["strategy"] = strategy_name
        backtest_status["message"] = "Initializing backtest..."
        
        # Create configuration
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            risk_per_trade=risk_per_trade,
            max_positions=max_positions,
            brokerage_per_trade=brokerage_per_trade
        )
        
        # Initialize engine
        engine = BacktestEngine(config)
        
        # Progress callback
        def progress_callback(progress: int, current_date: str):
            backtest_status["progress"] = progress
            backtest_status["current_date"] = current_date
            backtest_status["message"] = f"Processing {current_date}..."
        
        # Load strategy
        strategy = load_strategy(strategy_name)
        
        if not strategy:
            backtest_status["is_running"] = False
            backtest_status["message"] = f"Strategy '{strategy_name}' is not yet implemented for backtesting. Currently only 'pullback_entry' is supported."
            print(f"⚠️ Strategy '{strategy_name}' not available for backtesting")
            return
        
        backtest_status["message"] = "Running backtest..."
        
        # Run backtest in thread pool to avoid blocking the server
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool,
                engine.run,
                strategy,
                symbols,
                progress_callback
            )
        
        # Store result
        result_id = f"{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backtest_results[result_id] = result.to_dict()
        
        # Save to file
        output_dir = Path("data/backtests")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{result_id}.json"
        with open(output_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        backtest_status["message"] = f"Backtest complete! {result.total_trades} trades executed."
        backtest_status["progress"] = 100
        backtest_status["result_id"] = result_id
        
    except Exception as e:
        backtest_status["message"] = f"Error: {str(e)}"
        import traceback
        traceback.print_exc()
    
    finally:
        backtest_status["is_running"] = False


@router.get("/results")
async def get_backtest_results():
    """Get list of all backtest results"""
    try:
        output_dir = Path("data/backtests")
        
        if not output_dir.exists():
            return {"success": True, "results": [], "count": 0}
        
        results = []
        for file in output_dir.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    results.append({
                        "id": file.stem,
                        "strategy": data.get('strategy_name'),
                        "period": f"{data['config']['start_date']} to {data['config']['end_date']}",
                        "total_return": data.get('total_return'),
                        "total_return_pct": data.get('total_return_pct'),
                        "win_rate": data.get('win_rate'),
                        "total_trades": data.get('total_trades'),
                        "created": file.stat().st_mtime
                    })
            except:
                continue
        
        # Sort by creation time (newest first)
        results.sort(key=lambda x: x['created'], reverse=True)
        
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/results/{result_id}")
async def get_backtest_result(result_id: str):
    """Get detailed backtest result by ID"""
    try:
        # Check in-memory cache first
        if result_id in backtest_results:
            return {
                "success": True,
                "result": backtest_results[result_id]
            }
        
        # Load from file
        output_file = Path("data/backtests") / f"{result_id}.json"
        
        if not output_file.exists():
            return {"success": False, "error": "Backtest result not found"}
        
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        return {
            "success": True,
            "result": data
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/results/{result_id}")
async def delete_backtest_result(result_id: str):
    """Delete a backtest result"""
    try:
        output_file = Path("data/backtests") / f"{result_id}.json"
        
        if output_file.exists():
            output_file.unlink()
        
        # Remove from cache
        if result_id in backtest_results:
            del backtest_results[result_id]
        
        return {
            "success": True,
            "message": f"Backtest result {result_id} deleted"
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/strategies")
async def get_available_strategies():
    """Get list of strategies available for backtesting"""
    strategies = [
        {
            "id": "momentum_btst",
            "name": "Momentum BTST",
            "description": "1-3 day momentum breakout trades",
            "icon": "⚡"
        },
        {
            "id": "swing_supertrend",
            "name": "Swing SuperTrend",
            "description": "7-30 day trend following trades",
            "icon": "📈"
        },
        {
            "id": "mean_reversion",
            "name": "Mean Reversion",
            "description": "2-7 day oversold bounce trades",
            "icon": "🔄"
        },
        {
            "id": "pullback_entry",
            "name": "Pullback Entry",
            "description": "5-30 day pullback in uptrend trades",
            "icon": "🔵"
        },
        {
            "id": "swing_breakout_india",
            "name": "Swing Breakout (India)",
            "description": "NSE/BSE intraday breakout with RS",
            "icon": "🇮🇳"
        }
    ]
    
    return {
        "success": True,
        "strategies": strategies,
        "count": len(strategies)
    }


def load_strategy(strategy_name: str):
    """
    Load a strategy by name
    
    Args:
        strategy_name: Name of the strategy
        
    Returns:
        Strategy instance or None
    """
    try:
        if strategy_name == "pullback_entry":
            from strategies.pullback_entry import PullbackEntryStrategy
            return PullbackEntryStrategy()
        
        elif strategy_name == "momentum_btst":
            from strategies.momentum_btst import MomentumBTSTStrategy
            return MomentumBTSTStrategy()
        
        elif strategy_name == "swing_supertrend":
            from strategies.swing_supertrend import SwingSuperTrendStrategy
            return SwingSuperTrendStrategy()
        
        elif strategy_name == "mean_reversion":
            from strategies.mean_reversion import MeanReversionStrategy
            return MeanReversionStrategy()
        
        elif strategy_name == "swing_breakout_india":
            from strategies.swing_breakout_india import SwingBreakoutIndiaStrategy
            return SwingBreakoutIndiaStrategy()
        
        return None
    
    except Exception as e:
        print(f"Error loading strategy {strategy_name}: {e}")
        return None


@router.post("/quick-test")
async def run_quick_test(strategy: str, background_tasks: BackgroundTasks):
    """
    Run a quick backtest (last 3 months, all quality stocks)
    
    Args:
        strategy: Strategy name
        background_tasks: FastAPI background tasks
    """
    try:
        # Quick test configuration
        end_date = datetime.now()
        start_date = end_date.replace(month=end_date.month - 3) if end_date.month > 3 else end_date.replace(year=end_date.year - 1, month=end_date.month + 9)
        
        # Load top 20 symbols from quality watchlist
        # Use absolute path from project root
        project_root = Path(__file__).parent.parent.parent
        watchlist_path = project_root / "data" / "output" / "quality_watchlist.csv"
        
        if not watchlist_path.exists():
            return {
                "success": False,
                "error": f"Quality watchlist not found. Please generate it first."
            }
        
        import pandas as pd
        df = pd.read_csv(watchlist_path)
        # Use ALL symbols from watchlist (not just top 20)
        symbols = df['symbol'].tolist()
        symbols = [s if s.endswith('.NS') else f"{s}.NS" for s in symbols]
        
        # Create quick test request
        request = BacktestRequest(
            strategy=strategy,
            symbols=symbols,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            initial_capital=100000,
            risk_per_trade=2.0,
            max_positions=3,
            brokerage_per_trade=20.0
        )
        
        # Run backtest using the proper background_tasks injection
        return await run_backtest(request, background_tasks)
    
    except Exception as e:
        return {"success": False, "error": str(e)}

