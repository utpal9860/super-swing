"""
Main pattern scanner script
Scans stock universe and saves detected patterns to database
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import pandas as pd
from typing import List
import argparse

from config import PATTERN_CONFIG, BACKTEST_CONFIG
from utils.logger import setup_logger
from database.schema import create_database, insert_pattern
from pattern_detection.data_fetcher import (
    get_stock_universe, 
    batch_fetch_data,
    fetch_market_data
)
from pattern_detection.talib_patterns import (
    batch_scan_patterns,
    filter_high_quality_patterns
)

logger = setup_logger("scanner")

def run_pattern_scan(
    universe_type: str = "FNO",
    lookback_days: int = 730,  # 2 years
    recent_patterns_days: int = 30,
    save_to_db: bool = True,
    min_quality: float = 0.5
) -> List[dict]:
    """
    Run complete pattern scanning pipeline
    
    Args:
        universe_type: Stock universe type
        lookback_days: Days of historical data to fetch
        recent_patterns_days: Days to look for recent patterns
        save_to_db: Save patterns to database
        min_quality: Minimum pattern quality filter
    
    Returns:
        List of detected patterns
    """
    logger.info("="*60)
    logger.info("Starting Pattern Scan")
    logger.info("="*60)
    
    # Step 1: Get stock universe
    logger.info(f"Step 1: Getting {universe_type} stock universe...")
    tickers = get_stock_universe(universe_type)
    logger.info(f"Stock universe: {len(tickers)} stocks")
    
    # Step 2: Fetch historical data
    logger.info("Step 2: Fetching historical data...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    
    data_dict = batch_fetch_data(tickers, start_date, end_date, save_csv=True)
    logger.info(f"Fetched data for {len(data_dict)} stocks")
    
    # Step 3: Fetch market data
    logger.info("Step 3: Fetching market indices data...")
    market_data = fetch_market_data(start_date, end_date)
    logger.info(f"Fetched {len(market_data)} market indices")
    
    # Step 4: Scan for patterns
    logger.info("Step 4: Scanning for patterns...")
    all_patterns = batch_scan_patterns(
        list(data_dict.keys()),
        data_dict,
        exchange="NSE",
        lookback_days=recent_patterns_days
    )
    logger.info(f"Detected {len(all_patterns)} raw patterns")
    
    # Step 5: Filter high quality patterns
    logger.info("Step 5: Filtering high quality patterns...")
    quality_patterns = filter_high_quality_patterns(all_patterns, min_quality)
    logger.info(f"Filtered to {len(quality_patterns)} high-quality patterns")
    
    # Step 6: Save to database
    if save_to_db:
        logger.info("Step 6: Saving patterns to database...")
        create_database()  # Ensure DB exists
        
        saved_count = 0
        for pattern in quality_patterns:
            if insert_pattern(pattern):
                saved_count += 1
        
        logger.info(f"Saved {saved_count} patterns to database")
    
    # Summary
    logger.info("="*60)
    logger.info("Pattern Scan Complete!")
    logger.info(f"Total Patterns Detected: {len(all_patterns)}")
    logger.info(f"High Quality Patterns: {len(quality_patterns)}")
    logger.info(f"Saved to Database: {saved_count if save_to_db else 0}")
    logger.info("="*60)
    
    return quality_patterns

def scan_single_stock(ticker: str, lookback_days: int = 730) -> List[dict]:
    """
    Scan a single stock for patterns
    
    Args:
        ticker: Stock ticker
        lookback_days: Days of historical data
    
    Returns:
        List of detected patterns
    """
    from pattern_detection.data_fetcher import get_or_fetch_data
    from pattern_detection.talib_patterns import scan_stock_for_patterns
    
    logger.info(f"Scanning {ticker} for patterns...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    
    # Fetch data
    df = get_or_fetch_data(ticker, start_date, end_date)
    
    if df is None:
        logger.error(f"No data available for {ticker}")
        return []
    
    # Scan for patterns
    patterns = scan_stock_for_patterns(ticker, df, exchange="NSE", lookback_days=30)
    
    logger.info(f"Found {len(patterns)} patterns for {ticker}")
    return patterns

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pattern Scanner for Indian Stocks")
    parser.add_argument(
        "--universe", 
        type=str, 
        default="FNO",
        choices=["FNO", "NIFTY50", "NIFTY100", "ALL"],
        help="Stock universe to scan"
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=730,
        help="Days of historical data to fetch"
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=30,
        help="Days to look for recent patterns"
    )
    parser.add_argument(
        "--quality",
        type=float,
        default=0.5,
        help="Minimum pattern quality (0-1)"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Scan single stock ticker"
    )
    
    args = parser.parse_args()
    
    if args.ticker:
        # Scan single stock
        patterns = scan_single_stock(args.ticker, args.lookback)
        
        # Print results
        for p in patterns:
            print(f"\nPattern: {p['pattern_type']}")
            print(f"  Date: {p['detection_date']}")
            print(f"  Price: ₹{p['price_at_detection']:.2f}")
            print(f"  Confidence: {p['confidence_score']:.2f}")
    else:
        # Full scan
        patterns = run_pattern_scan(
            universe_type=args.universe,
            lookback_days=args.lookback,
            recent_patterns_days=args.recent,
            save_to_db=True,
            min_quality=args.quality
        )

