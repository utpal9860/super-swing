# Troubleshooting Guide - ML Pattern Trading System

## ✅ **Fixed Issues**

### Issue 1: `'atr_14'` KeyError
**Error**: `KeyError: 'atr_14'`  
**Cause**: Technical indicators not calculated before feature engineering  
**Fix**: ✅ Auto-calculates indicators if missing  
**Status**: FIXED

### Issue 2: `'Close'` KeyError  
**Error**: `KeyError: 'Close'`  
**Cause**: Column name mismatch (capitalized vs lowercase)  
**Fix**: ✅ All columns normalized to lowercase  
**Status**: FIXED

---

## 🔧 **Common Issues & Solutions**

### 1. "No patterns detected"

**Symptoms**:
```
Found 0 patterns
```

**Solutions**:
```bash
# Check if TA-Lib is installed
python -c "import talib; print('TA-Lib OK')"

# If not installed:
# Windows: Download from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
# Linux: sudo apt-get install ta-lib
# Mac: brew install ta-lib

pip install TA-Lib
```

### 2. "No features engineered"

**Symptoms**:
```
Engineered features for 0 patterns
No features were successfully generated
```

**Solutions**:
```python
# Check data quality
python -c "
from pattern_detection.data_fetcher import fetch_historical_data
from datetime import datetime, timedelta

df = fetch_historical_data('RELIANCE', datetime.now() - timedelta(days=365), datetime.now())
print(f'Data shape: {df.shape}')
print(f'Columns: {df.columns.tolist()}')
print(f'First few rows:\n{df.head()}')
"
```

**Common causes**:
- ❌ Not enough historical data (need 20+ days)
- ❌ Column names not lowercase
- ❌ Data has NaN values
- ❌ Insufficient data at pattern index

**Fix**:
- Ensure at least 2 years of data
- Check column names are lowercase
- Verify data quality before pattern detection

### 3. "Model not trained"

**Symptoms**:
```
Model not trained. Call train() first.
```

**Solutions**:
```bash
# You need to train models first!
# Option 1: Review patterns and train
python run_complete_workflow.py review  # Review 500+ patterns
python run_complete_workflow.py train   # Train models

# Option 2: For testing, run without models
python signal_generator.py --universe FNO  # Works without models (no ML filtering)
```

### 4. "Empty signals DataFrame"

**Symptoms**:
```
No signals generated today.
```

**Causes & Solutions**:

**A. No patterns found**:
```python
# Lower quality threshold
# In pattern_detection/scanner.py, change:
quality_patterns = filter_high_quality_patterns(all_patterns, min_quality=0.3)  # Was 0.5
```

**B. Patterns filtered out by models**:
```python
# Models too strict - train with more data or adjust thresholds
# In config.py:
SIGNAL_CONFIG = {
    "min_success_probability": 0.50,  # Lower from 0.60
    "min_expected_gain": 2.0,          # Lower from 3.0
}
```

**C. No recent patterns**:
```bash
# Increase lookback
python run_complete_workflow.py scan --recent 7  # Look back 7 days instead of 5
```

### 5. "Import Error: ultralytics"

**Symptoms**:
```
ModuleNotFoundError: No module named 'ultralytics'
```

**Solution**:
```bash
# YOLOv8 is optional - only needed for chart pattern detection
pip install ultralytics mss opencv-python

# Or skip YOLOv8 integration if you don't need it
```

### 6. Database Errors

**Symptoms**:
```
sqlite3.OperationalError: no such table: patterns
```

**Solution**:
```bash
# Recreate database
python run_complete_workflow.py setup
```

### 7. "Too many patterns to review"

**Symptoms**:
- Review interface shows 5,000 patterns
- Overwhelming amount of work

**Solution**:
```python
# Scan with shorter recent window
python run_complete_workflow.py scan --recent 5  # Only last 5 days

# Or review in batches
# In review_interface/app.py:
patterns = get_pending_patterns(limit=50)  # Review 50 at a time
```

---

## 🐛 **Debug Mode**

### Enable Detailed Logging

```python
# In config.py
LOGGING_CONFIG = {
    "level": "DEBUG",  # Change from INFO to DEBUG
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": LOGS_DIR / "ml_system.log",
}
```

### Check Logs

```bash
# View real-time logs
tail -f ML/logs/ml_system.log

# Windows PowerShell
Get-Content ML/logs/ml_system.log -Wait -Tail 50
```

### Test Individual Components

```bash
# Test data fetching
python -c "
from pattern_detection.data_fetcher import fetch_historical_data
from datetime import datetime, timedelta
df = fetch_historical_data('RELIANCE', datetime.now() - timedelta(days=365), datetime.now())
print('Data fetching:', 'OK' if df is not None else 'FAILED')
"

# Test pattern detection
python pattern_detection/scanner.py --ticker RELIANCE

# Test feature engineering
python -c "
from feature_engineering.features import calculate_stock_features
import pandas as pd
from datetime import datetime, timedelta
from pattern_detection.data_fetcher import fetch_historical_data

df = fetch_historical_data('RELIANCE', datetime.now() - timedelta(days=365), datetime.now())
features = calculate_stock_features(df, len(df)-1)
print('Features:', features)
"
```

---

## 📊 **Performance Issues**

### Slow Pattern Scanning

**Issue**: Scanning takes 30+ minutes

**Solutions**:
```python
# 1. Reduce stock universe
tickers = get_stock_universe("NIFTY50")[:20]  # Only 20 stocks

# 2. Use cached data
get_or_fetch_data(ticker, start_date, end_date, use_cache=True)

# 3. Parallel processing (advanced)
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=4) as executor:
    results = executor.map(scan_stock, tickers)
```

### High Memory Usage

**Issue**: System uses >4GB RAM

**Solutions**:
```python
# Process in batches
batch_size = 10
for i in range(0, len(tickers), batch_size):
    batch = tickers[i:i+batch_size]
    scan_batch(batch)
    # Clear memory
    del batch
    import gc; gc.collect()
```

---

## 🔍 **Data Quality Checks**

### Verify Data Integrity

```python
# Run data quality checks
from utils.data_utils import validate_data_quality, clean_data

df = fetch_stock_data('RELIANCE', start_date, end_date)

# Check quality
is_valid = validate_data_quality(df)
print(f"Data valid: {is_valid}")

# Clean data
df_clean = clean_data(df)
print(f"Original: {len(df)}, Cleaned: {len(df_clean)}")
```

---

## ⚠️ **Known Limitations**

### 1. No Real-Time Data
- System uses end-of-day data
- Not suitable for intraday trading
- Solution: Use for swing trading (3-20 days holding)

### 2. Pattern Detection Lag
- Patterns detected after formation complete
- Entry is next day open
- Solution: This is realistic - no lookahead bias

### 3. Limited to TA-Lib Patterns
- Only candlestick patterns (60+)
- No complex chart patterns (H&S, triangles) without YOLOv8
- Solution: Add YOLOv8 integration for chart patterns

### 4. Requires Manual Review
- Need 500-1000 validated patterns
- Takes 2-3 weeks
- Solution: This is the price of quality - can't skip this

---

## 🆘 **Still Having Issues?**

### 1. Check Your Setup

```bash
# Verify installation
python -c "
import sys
print(f'Python: {sys.version}')

try:
    import pandas; print('pandas: OK')
except: print('pandas: MISSING')

try:
    import numpy; print('numpy: OK')
except: print('numpy: MISSING')

try:
    import talib; print('TA-Lib: OK')
except: print('TA-Lib: MISSING')

try:
    import sklearn; print('scikit-learn: OK')
except: print('scikit-learn: MISSING')

try:
    import xgboost; print('XGBoost: OK')
except: print('XGBoost: MISSING (optional)')
"
```

### 2. Clean Start

```bash
# Nuclear option - start fresh
rm -rf ML/data/patterns.db  # Delete database
rm -rf ML/data/raw/*        # Delete cached data
rm -rf ML/logs/*            # Delete logs

python run_complete_workflow.py setup  # Reinitialize
```

### 3. Check Python Version

```bash
# Requires Python 3.8+
python --version

# If < 3.8, upgrade:
# Use pyenv or conda to manage Python versions
```

---

## 📝 **Getting Help**

### What to Include in Bug Reports

1. **Error message** (full traceback)
2. **Command you ran**
3. **System info** (OS, Python version)
4. **Log file** (`ML/logs/ml_system.log`)
5. **What you expected** vs **what happened**

### Quick Health Check

```bash
python -c "
print('='*50)
print('ML SYSTEM HEALTH CHECK')
print('='*50)

# Check directories
from pathlib import Path
print(f'ML directory exists: {Path(\"ML\").exists()}')
print(f'Database exists: {Path(\"ML/data/patterns.db\").exists()}')
print(f'Models directory: {Path(\"ML/models\").exists()}')

# Check database
try:
    from database.schema import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM patterns')
    count = cursor.fetchone()[0]
    print(f'Patterns in DB: {count}')
    conn.close()
except Exception as e:
    print(f'Database error: {e}')

print('='*50)
"
```

---

## ✅ **System Status**

After all fixes, the system should:
- ✅ Detect patterns without column errors
- ✅ Calculate technical indicators automatically
- ✅ Handle missing data gracefully
- ✅ Generate features for 700+ patterns
- ✅ Work without trained models (for testing)
- ✅ Log detailed information

**If you see "Engineered features for 775 patterns" - YOU'RE GOOD TO GO!** 🎉

The system is working. If no signals are generated, it just means:
- Either no high-quality patterns found
- Or models (if loaded) filtered them out
- Try lowering thresholds in `config.py`

---

**Last Updated**: October 30, 2025  
**Status**: All critical bugs fixed ✅

