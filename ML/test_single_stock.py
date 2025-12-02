"""
Test Pattern Detection on Single Stock
Debug script with detailed error logging
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import traceback

# Setup logging
from utils.logger import setup_logger
logger = setup_logger("test_single_stock")
logger.setLevel("DEBUG")

print("="*80)
print("SINGLE STOCK PATTERN DETECTION TEST")
print("="*80)

# Test stock
TEST_TICKER = "RELIANCE"
print(f"\nTest Ticker: {TEST_TICKER}")

# Step 1: Fetch Data
print("\n" + "="*80)
print("STEP 1: Fetching Historical Data")
print("="*80)

try:
    from pattern_detection.data_fetcher import fetch_stock_data
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years
    
    print(f"Date Range: {start_date.date()} to {end_date.date()}")
    
    df = fetch_stock_data(TEST_TICKER, start_date, end_date)
    
    if df is None or df.empty:
        print("[FAILED] No data fetched")
        sys.exit(1)
    
    print(f"[SUCCESS] Fetched {len(df)} rows")
    print(f"\nColumn Names: {df.columns.tolist()}")
    print(f"\nData Types:\n{df.dtypes}")
    print(f"\nFirst 3 rows:\n{df.head(3)}")
    print(f"\nLast 3 rows:\n{df.tail(3)}")
    print(f"\nNull Values:\n{df.isnull().sum()}")
    
except Exception as e:
    print(f"[ERROR] in data fetching: {e}")
    print(traceback.format_exc())
    sys.exit(1)

# Step 2: Detect Patterns
print("\n" + "="*80)
print("STEP 2: Detecting Patterns with TA-Lib")
print("="*80)

try:
    from pattern_detection.talib_patterns import scan_stock_for_patterns
    
    patterns = scan_stock_for_patterns(
        ticker=TEST_TICKER,
        df=df.copy(),
        exchange="NSE",
        lookback_days=30
    )
    
    print(f"[SUCCESS] Found {len(patterns)} patterns")
    
    if patterns:
        print(f"\nSample Pattern:")
        sample = patterns[0]
        for key, value in sample.items():
            print(f"  {key}: {value}")
    
except Exception as e:
    print(f"[ERROR] in pattern detection: {e}")
    print(traceback.format_exc())
    sys.exit(1)

# Step 3: Calculate Technical Indicators
print("\n" + "="*80)
print("STEP 3: Calculating Technical Indicators")
print("="*80)

try:
    from pattern_detection.talib_patterns import calculate_technical_indicators
    
    df_with_indicators = calculate_technical_indicators(df.copy())
    
    print(f"[SUCCESS] Indicators calculated")
    print(f"\nColumns after indicators: {df_with_indicators.columns.tolist()}")
    print(f"\nIndicator values (last row):")
    
    indicator_cols = ['rsi_14', 'atr_14', 'volume_ratio', 'sma_20', 'sma_50', 'sma_200']
    last_row = df_with_indicators.iloc[-1]
    
    for col in indicator_cols:
        if col in df_with_indicators.columns:
            value = last_row[col]
            print(f"  {col}: {value}")
        else:
            print(f"  {col}: MISSING!")
    
except Exception as e:
    print(f"[ERROR] in indicator calculation: {e}")
    print(traceback.format_exc())
    sys.exit(1)

# Step 4: Engineer Features for One Pattern
print("\n" + "="*80)
print("STEP 4: Engineering Features for Sample Pattern")
print("="*80)

if not patterns:
    print("[SKIPPED] No patterns to test")
else:
    try:
        from feature_engineering.features import engineer_features_for_pattern
        
        # Test with first pattern
        test_pattern = patterns[0]
        print(f"\nTesting pattern: {test_pattern['pattern_type']}")
        print(f"Detection date: {test_pattern['detection_date']}")
        
        # Prepare data - ensure lowercase columns
        df_for_features = df.copy()
        print(f"\nBEFORE lowercase - columns: {df_for_features.columns.tolist()}")
        df_for_features.columns = df_for_features.columns.str.lower()
        print(f"AFTER lowercase - columns: {df_for_features.columns.tolist()}")
        
        print(f"Data shape: {df_for_features.shape}")
        
        # Check for required columns
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df_for_features.columns]
        
        if missing_cols:
            print(f"[FAILED] Missing columns: {missing_cols}")
            sys.exit(1)
        
        print(f"[OK] All required columns present")
        
        # Engineer features
        print("\nEngineering features...")
        features = engineer_features_for_pattern(
            pattern_data=test_pattern,
            stock_data=df_for_features,
            market_data=None  # Skip market data for now
        )
        
        if not features:
            print("[FAILED] No features generated")
            print("\nDebugging info:")
            print(f"  Pattern date: {test_pattern['detection_date']}")
            print(f"  Data date range: {df_for_features['date'].min()} to {df_for_features['date'].max()}")
            
            # Find pattern date in data
            pattern_date = pd.to_datetime(test_pattern['detection_date'])
            df_for_features['date'] = pd.to_datetime(df_for_features['date'])
            idx = (df_for_features['date'] - pattern_date).abs().argmin()
            print(f"  Closest index: {idx} out of {len(df_for_features)}")
            print(f"  Has enough history: {idx >= 20}")
            
        else:
            print(f"[SUCCESS] Generated {len(features)} features")
            print("\nSample features:")
            for i, (key, value) in enumerate(features.items()):
                if i < 10:  # Show first 10
                    print(f"  {key}: {value}")
            if len(features) > 10:
                print(f"  ... and {len(features) - 10} more features")
        
    except Exception as e:
        print(f"[ERROR] in feature engineering: {e}")
        print("\nFull traceback:")
        print(traceback.format_exc())
        
        # Additional debugging
        print("\nDebug Info:")
        print(f"  Pattern data type: {type(test_pattern)}")
        print(f"  Pattern keys: {test_pattern.keys() if isinstance(test_pattern, dict) else 'N/A'}")
        print(f"  Stock data shape: {df_for_features.shape}")
        print(f"  Stock data columns: {df_for_features.columns.tolist()}")
        print(f"  Stock data dtypes:\n{df_for_features.dtypes}")
        
        sys.exit(1)

# Step 5: Test Feature Engineering for All Patterns
print("\n" + "="*80)
print("STEP 5: Engineering Features for All Patterns")
print("="*80)

try:
    from feature_engineering.features import create_feature_dataframe
    
    # Create data dict
    data_dict = {TEST_TICKER: df.copy()}
    
    # Ensure lowercase
    data_dict[TEST_TICKER].columns = data_dict[TEST_TICKER].columns.str.lower()
    
    print(f"\nProcessing {len(patterns)} patterns...")
    
    features_df = create_feature_dataframe(
        patterns=patterns,
        data_dict=data_dict,
        market_data=None
    )
    
    if features_df.empty:
        print("[FAILED] Feature DataFrame is empty")
        print("\nDebugging:")
        print(f"  Input patterns: {len(patterns)}")
        print(f"  Output features: {len(features_df)}")
    else:
        print(f"[SUCCESS] Feature DataFrame created")
        print(f"  Shape: {features_df.shape}")
        print(f"  Columns: {len(features_df.columns)}")
        print(f"\nFeature columns:")
        for col in features_df.columns[:20]:  # First 20
            print(f"  - {col}")
        if len(features_df.columns) > 20:
            print(f"  ... and {len(features_df.columns) - 20} more")
    
except Exception as e:
    print(f"[ERROR] in batch feature engineering: {e}")
    print(traceback.format_exc())
    sys.exit(1)

# Summary
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)

print(f"""
[OK] Data Fetching: SUCCESS ({len(df)} rows)
[OK] Pattern Detection: SUCCESS ({len(patterns)} patterns)
[OK] Technical Indicators: SUCCESS
[OK] Feature Engineering: {'SUCCESS' if not features_df.empty else 'FAILED'}

Stock: {TEST_TICKER}
Patterns Found: {len(patterns)}
Features Generated: {len(features_df) if not features_df.empty else 0}
Feature Columns: {len(features_df.columns) if not features_df.empty else 0}
""")

if features_df.empty:
    print("[WARNING] Feature engineering produced empty DataFrame")
    print("   This means patterns are being detected but features can't be calculated")
    print("   Check the error logs above for details")
else:
    print("[SUCCESS] ALL TESTS PASSED!")
    print("\nYour system is working correctly for single stock.")
    print("You can now run the full scanner on all stocks.")

print("\n" + "="*80)
