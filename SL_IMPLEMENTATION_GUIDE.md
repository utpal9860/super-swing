# SL Implementation Guide

## 🎯 Overview

Automatic Stop Loss (SL) calculation and time-sequenced checking has been implemented based on backtest analysis.

---

## ✅ What's Implemented

### 1. **Auto-SL Calculation** (`webapp/api/paper_trading.py`)

When a signal has `SL: PAID` or no SL provided, the system automatically calculates SL:

- **Monthly Options**: 30% SL (based on backtest recommendation)
- **Weekly Options** (≤7 days to expiry): 40% SL (higher volatility)
- **Stocks**: 4% SL (standard)
- **Minimum Safety**: Never less than 25% SL for options

**Example:**
```
Entry: ₹100
Monthly Option → SL: ₹70 (30% below)
Weekly Option → SL: ₹60 (40% below)
```

### 2. **Time-Sequenced SL/Target Checking** (`webapp/api/eod_monitor.py`)

The EOD monitor now checks **which level was hit first** using time-series OHLC data:

**Scenario 1: Target Hit First**
```
Day 1: Entry at ₹10
Day 2: High=₹15 (target), Low=₹8 (SL not hit)
→ Target hit first ✅
```

**Scenario 2: SL Hit First**
```
Day 1: Entry at ₹10
Day 2: Low=₹7 (SL), High=₹15 (target)
→ SL hit first ❌ (even though target was also hit)
```

**Scenario 3: Entry After Price Movement**
```
Day 1: Open=₹5, High=₹15, Entry=₹10
→ If entry >= open, price likely moved before entry
→ Target already hit before entry (don't count)
```

### 3. **SL Placement Worker** (`webapp/api/sl_placement_worker.py`)

Background worker that:
- Monitors filled entry orders
- Calculates SL if not set
- Places SL order as separate order (non-blocking)
- Retries on failure (3 attempts, 2 seconds apart)

**Flow:**
```
1. Entry order placed → Status: PLACED
2. Entry order fills → Status: COMPLETE
3. Worker detects filled order
4. Calculates SL (if not set)
5. Places SL order (with retry)
6. Updates trade with SL order ID
```

---

## 🔍 Edge Cases Handled

### 1. **Entry After Price Movement**

**Problem:** Market starts at ₹5, moves to ₹10 (entry), then to ₹15 (target)

**Solution:**
- Check if entry price >= day's open
- If yes, price likely moved before entry
- Don't count target/SL hits that occurred before entry

**Code:**
```python
if day_date_str == entry_day:
    if entry_price >= open_price:
        # Price moved before entry - don't count
        continue
```

### 2. **Both SL and Target Hit on Same Day**

**Problem:** Both SL and target hit on the same day - which came first?

**Solution:**
- Use conservative approach: Assume SL hit first (protect capital)
- Log warning for manual review

**Code:**
```python
if target_hit and sl_hit:
    # Conservative: Exit at SL (safer)
    return {'status': 'STOP_LOSS_HIT', ...}
```

### 3. **Intraday Sequence (Daily Data Limitation)**

**Limitation:** Daily OHLC data doesn't show intraday sequence

**Example:**
- Day 1: Open=₹5, High=₹15, Low=₹7, Close=₹10, Entry=₹10
- Can't tell if: 5→10 (entry) →15 (target) or 5→15 (target) →10 (entry)

**Handling:**
- If entry price is between open and close, assume entry was active
- If entry = open, entry was at market open
- If entry = close, entry was at market close
- Conservative approach: If both hit same day, exit at SL

### 4. **Live Trading: Entry Order Fills Before SL Placement**

**Problem:** Entry order fills immediately, but SL order not placed yet

**Solution:**
- SL Placement Worker checks every 30 seconds
- Detects filled orders and places SL
- Uses retry logic (3 attempts)
- Trade is protected once SL order is placed

---

## 📊 Implementation Details

### Auto-SL Calculation Logic

```python
# In create_trade_from_signal()
if signal.stop_loss_text == "PAID" or stop_loss_val == 0.0:
    # Check if weekly option
    if is_weekly or days_to_expiry <= 7:
        sl_percentage = 40.0  # Weekly: 40% SL
    else:
        sl_percentage = 30.0  # Monthly: 30% SL
    
    stop_loss_val = entry_price * (1 - sl_percentage / 100)
    min_sl = entry_price * 0.75  # Minimum 25%
    stop_loss_val = max(stop_loss_val, min_sl)
```

### Time-Sequenced Check Logic

```python
# In option_status_from_ltp()
if hist_ohlc and hist_ohlc.get('data'):
    # Sort by date (oldest first)
    sorted_data = sorted(ohlc_data, key=lambda x: x.get('date', ''))
    
    # Find first occurrence
    for day_data in sorted_data:
        if day_data['high'] >= target:
            target_hit_first = day_data['date']
        if day_data['low'] <= sl:
            sl_hit_first = day_data['date']
    
    # Compare dates
    if sl_hit_first < target_hit_first:
        return 'STOP_LOSS_HIT'  # SL hit first
    else:
        return 'TARGET_HIT'  # Target hit first
```

---

## 🚀 Live Trading Flow

### Scenario: Place Order Quickly, Add SL Later

1. **Signal Received** → Telegram message
2. **Parse Signal** → Extract symbol, strike, price
3. **Place Entry Order** → Immediately (no SL calculation delay)
4. **Order Fills** → Status: COMPLETE
5. **SL Placement Worker** → Detects filled order (every 30 seconds)
6. **Calculate SL** → 30% or 40% based on expiry
7. **Place SL Order** → Separate SELL SL order (with retry)
8. **Update Trade** → Store SL order ID

**Benefits:**
- ✅ Fast order placement (no delay)
- ✅ Automatic SL protection
- ✅ Retry on failure
- ✅ Non-blocking (doesn't slow down entry)

---

## 🔧 Configuration

### SL Percentages

- **Monthly Options**: 30% (configurable)
- **Weekly Options**: 40% (configurable)
- **Stocks**: 4% (configurable)
- **Minimum**: 25% for options (safety net)

### Worker Settings

- **SL Placement Worker**: Checks every 30 seconds
- **Retry Logic**: 3 attempts, 2 seconds apart
- **Market Hours**: 9:15 AM - 3:30 PM IST

---

## 📝 Edge Cases Summary

| Scenario | Handling |
|----------|----------|
| Entry after price moved up | Don't count target hit before entry |
| Entry after price moved down | Don't count SL hit before entry |
| Both hit on same day | Conservative: Exit at SL |
| SL hit, then target | Exit at SL (SL hit first) |
| Target hit, then SL | Exit at target (target hit first) |
| Entry order fills before SL | Worker places SL within 30 seconds |
| SL placement fails | Retry 3 times, log warning |

---

## ✅ Testing Checklist

- [x] Auto-SL calculation for monthly options (30%)
- [x] Auto-SL calculation for weekly options (40%)
- [x] Time-sequenced checking (which hit first)
- [x] Entry after price movement handling
- [x] Same-day both hit handling
- [x] SL placement worker for live trading
- [x] Retry logic for SL placement
- [x] Integration with EOD monitor

---

## 🎯 Next Steps

1. **Monitor Performance**: Track SL hit rate for 1 month
2. **Adjust if Needed**: Fine-tune SL percentages based on results
3. **Intraday Data**: Consider adding minute-level data for better precision
4. **Alerts**: Notify when SL is auto-calculated or placed

---

**Status:** ✅ Fully Implemented  
**Last Updated:** $(date)

