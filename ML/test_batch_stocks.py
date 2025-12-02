"""
Test Pattern Detection on Multiple Stocks
Find which stocks are causing errors
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import pandas as pd
from datetime import datetime, timedelta
import traceback

from utils.logger import setup_logger
logger = setup_logger("test_batch")

# Test with small batch
TEST_STOCKS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

print("="*80)
print(f"BATCH TEST: {len(TEST_STOCKS)} stocks")
print("="*80)

from pattern_detection.data_fetcher import batch_fetch_data, get_stock_universe
from pattern_detection.talib_patterns import batch_scan_patterns
from feature_engineering.features import create_feature_dataframe

# Step 1: Fetch data for all stocks
print("\nStep 1: Fetching data...")
end_date = datetime.now()
start_date = end_date - timedelta(days=365*2)

data_dict = {}
failed_stocks = []

for ticker in TEST_STOCKS:
    try:
        from pattern_detection.data_fetcher import fetch_stock_data
        df = fetch_stock_data(ticker, start_date, end_date)
        if df is not None and not df.empty:
            # Ensure lowercase
            df.columns = df.columns.str.lower()
            data_dict[ticker] = df
            print(f"[OK] {ticker}: {len(df)} rows")
        else:
            print(f"[SKIP] {ticker}: No data")
            failed_stocks.append(ticker)
    except Exception as e:
        print(f"[ERROR] {ticker}: {e}")
        failed_stocks.append(ticker)

print(f"\nData fetched: {len(data_dict)}/{len(TEST_STOCKS)} stocks")
print(f"Failed stocks: {failed_stocks}")

# Step 2: Scan for patterns
print("\nStep 2: Scanning patterns...")
all_patterns = batch_scan_patterns(
    list(data_dict.keys()),
    data_dict,
    exchange="NSE",
    lookback_days=30
)

print(f"Total patterns found: {len(all_patterns)}")

# Group by ticker
from collections import defaultdict
patterns_by_ticker = defaultdict(list)
for p in all_patterns:
    patterns_by_ticker[p['ticker']].append(p)

print("\nPatterns per stock:")
for ticker, patterns in patterns_by_ticker.items():
    print(f"  {ticker}: {len(patterns)} patterns")

# Step 3: Feature engineering with detailed error tracking
print("\nStep 3: Feature engineering...")
print("Testing each stock individually to find problematic ones...")

successful_stocks = []
failed_feature_stocks = []

for ticker in data_dict.keys():
    try:
        ticker_patterns = patterns_by_ticker[ticker]
        if not ticker_patterns:
            print(f"  {ticker}: No patterns, skipping")
            continue
        
        # Test feature engineering for this stock
        single_data_dict = {ticker: data_dict[ticker]}
        
        features_df = create_feature_dataframe(
            patterns=ticker_patterns,
            data_dict=single_data_dict,
            market_data=None
        )
        
        if features_df.empty:
            print(f"  {ticker}: [FAILED] No features generated ({len(ticker_patterns)} patterns)")
            failed_feature_stocks.append(ticker)
        else:
            print(f"  {ticker}: [OK] {len(features_df)} features from {len(ticker_patterns)} patterns")
            successful_stocks.append(ticker)
            
    except Exception as e:
        print(f"  {ticker}: [ERROR] {e}")
        failed_feature_stocks.append(ticker)
        print(f"    Traceback: {traceback.format_exc()}")

# Step 4: Try batch processing
print("\nStep 4: Batch feature engineering...")
try:
    features_df_batch = create_feature_dataframe(
        patterns=all_patterns,
        data_dict=data_dict,
        market_data=None
    )
    
    if features_df_batch.empty:
        print("[FAILED] Batch feature engineering returned empty DataFrame")
        print(f"  Input patterns: {len(all_patterns)}")
    else:
        print(f"[SUCCESS] Batch processing worked!")
        print(f"  Features: {features_df_batch.shape}")
        
except Exception as e:
    print(f"[ERROR] Batch feature engineering failed: {e}")
    print(traceback.format_exc())

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"""
Stocks tested: {len(TEST_STOCKS)}
Data fetched: {len(data_dict)} 
Failed data fetch: {len(failed_stocks)}

Patterns detected: {len(all_patterns)}
Successful feature eng: {len(successful_stocks)}
Failed feature eng: {len(failed_feature_stocks)}

Stocks with issues:
  Data fetch failures: {failed_stocks}
  Feature eng failures: {failed_feature_stocks}
""")

if failed_feature_stocks:
    print("\n[ACTION NEEDED] These stocks are causing feature engineering to fail:")
    for ticker in failed_feature_stocks:
        print(f"  - {ticker}")
        if ticker in data_dict:
            df = data_dict[ticker]
            print(f"      Data shape: {df.shape}")
            print(f"      Columns: {df.columns.tolist()}")
            print(f"      Patterns: {len(patterns_by_ticker[ticker])}")
else:
    print("\n[SUCCESS] All stocks processed successfully!")

print("="*80)

