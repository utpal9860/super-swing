"""
Watchlist API
Manages quality watchlist operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path
import logging
import subprocess
import pandas as pd
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

# Watchlist generation status
watchlist_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_stock": "",
    "qualified_count": 0,
    "last_updated": None
}


class WatchlistRequest(BaseModel):
    """Watchlist generation request"""
    max_analyze: Optional[int] = None
    min_score: int = 50
    parallel: int = 20


@router.get("/status")
async def get_watchlist_status():
    """Get watchlist generation status"""
    return {"success": True, "status": watchlist_status}


@router.get("/symbols")
async def get_watchlist_symbols():
    """Get list of symbols from quality watchlist"""
    try:
        watchlist_file = OUTPUT_DIR / "quality_watchlist.csv"
        
        if not watchlist_file.exists():
            return {
                "success": False,
                "error": "Quality watchlist not found. Please generate it first.",
                "symbols": []
            }
        
        # Read watchlist
        df = pd.read_csv(watchlist_file)
        
        # Extract symbols (check common column names)
        if 'symbol' in df.columns:
            symbols = df['symbol'].tolist()
        elif 'Symbol' in df.columns:
            symbols = df['Symbol'].tolist()
        else:
            symbols = df.iloc[:, 0].tolist()  # First column
        
        return {
            "success": True,
            "symbols": symbols,
            "count": len(symbols)
        }
    
    except Exception as e:
        logger.error(f"Error loading watchlist symbols: {e}")
        return {
            "success": False,
            "error": str(e),
            "symbols": []
        }


@router.get("/current")
async def get_current_watchlist():
    """Get current quality watchlist"""
    try:
        watchlist_file = OUTPUT_DIR / "quality_watchlist.csv"
        
        if not watchlist_file.exists():
            return {
                "success": True,
                "stocks": [],
                "count": 0,
                "message": "No watchlist found. Generate one first."
            }
        
        df = pd.read_csv(watchlist_file)
        stocks = df.to_dict('records')
        
        # Get file modification time
        updated_time = datetime.fromtimestamp(watchlist_file.stat().st_mtime)
        
        return {
            "success": True,
            "stocks": stocks,
            "count": len(stocks),
            "last_updated": updated_time.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    except Exception as e:
        logger.error(f"Error reading watchlist: {e}")
        return {
            "success": False,
            "error": str(e),
            "stocks": [],
            "count": 0
        }


@router.get("/top/{n}")
async def get_top_stocks(n: int):
    """Get top N stocks from watchlist"""
    try:
        watchlist_file = OUTPUT_DIR / "quality_watchlist.csv"
        
        if not watchlist_file.exists():
            return {
                "success": True,
                "stocks": [],
                "count": 0,
                "message": "No watchlist found"
            }
        
        df = pd.read_csv(watchlist_file)
        top_stocks = df.head(n).to_dict('records')
        
        return {
            "success": True,
            "stocks": top_stocks,
            "count": len(top_stocks)
        }
    
    except Exception as e:
        logger.error(f"Error reading top stocks: {e}")
        return {
            "success": False,
            "error": str(e),
            "stocks": [],
            "count": 0
        }


@router.post("/generate")
async def generate_watchlist(request: WatchlistRequest, background_tasks: BackgroundTasks):
    """Generate/update quality watchlist"""
    if watchlist_status["is_running"]:
        raise HTTPException(status_code=400, detail="Watchlist generation is already running")
    
    # Run generation in background
    background_tasks.add_task(
        execute_watchlist_generation,
        request.max_analyze,
        request.min_score,
        request.parallel
    )
    
    return {
        "success": True,
        "message": "Watchlist generation started. This may take 15-20 minutes. Check /api/watchlist/status for progress."
    }


async def execute_watchlist_generation(max_analyze: Optional[int], min_score: int, parallel: int):
    """Execute the watchlist generation script"""
    global watchlist_status
    
    watchlist_status["is_running"] = True
    watchlist_status["progress"] = 0
    watchlist_status["qualified_count"] = 0
    watchlist_status["current_stock"] = "Starting generation..."
    
    try:
        # Build command
        cmd = [
            "python",
            "create_quality_watchlist.py",
            "--min-score", str(min_score),
            "--parallel", str(parallel)
        ]
        
        if max_analyze:
            cmd.extend(["--max-analyze", str(max_analyze)])
        
        logger.info(f"Generating watchlist: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=Path(__file__).parent.parent.parent
        )
        
        if result.returncode == 0:
            # Parse output to get qualified count
            output = result.stdout
            if "Qualified:" in output:
                for line in output.split('\n'):
                    if "Qualified:" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "Qualified:":
                                watchlist_status["qualified_count"] = int(parts[i+1])
                                break
            
            watchlist_status["last_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"Watchlist generation completed. Qualified: {watchlist_status['qualified_count']} stocks")
        else:
            logger.error(f"Watchlist generation failed: {result.stderr}")
            watchlist_status["current_stock"] = f"Error: {result.stderr[:100]}"
    
    except Exception as e:
        logger.error(f"Error generating watchlist: {e}")
        watchlist_status["current_stock"] = f"Error: {str(e)}"
    
    finally:
        watchlist_status["is_running"] = False
        watchlist_status["progress"] = 100


@router.get("/search/{query}")
async def search_watchlist(query: str):
    """Search for stocks in watchlist"""
    try:
        watchlist_file = OUTPUT_DIR / "quality_watchlist.csv"
        
        if not watchlist_file.exists():
            return {
                "success": True,
                "stocks": [],
                "count": 0
            }
        
        df = pd.read_csv(watchlist_file)
        
        # Search in symbol column
        matches = df[df['symbol'].str.contains(query.upper(), case=False, na=False)]
        results = matches.to_dict('records')
        
        return {
            "success": True,
            "stocks": results,
            "count": len(results),
            "query": query
        }
    
    except Exception as e:
        logger.error(f"Error searching watchlist: {e}")
        return {
            "success": False,
            "error": str(e),
            "stocks": [],
            "count": 0
        }

