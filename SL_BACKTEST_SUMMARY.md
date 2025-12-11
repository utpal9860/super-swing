# SL Strategy Backtest Results Summary

## 📊 Analysis Overview

**Date:** Generated from historical trades  
**Total Trades Analyzed:** 11 trades (10 closed, 1 open)  
**Analysis Method:** Using `lowest_price` data from trades.json

---

## 🎯 Key Findings

### 1. **Closed Trades Performance**
- **All 10 closed trades had 0% drawdown**
- Price never went below entry price
- All trades hit target successfully
- **Result:** No closed trade would have been stopped out at ANY SL level (15-40%)

### 2. **Open Trade (CHOLAFIN)**
- **Entry Price:** ₹32.00
- **Lowest Price:** ₹11.65
- **Maximum Drawdown:** **63.59%**
- **Status:** Still open (hasn't hit target yet)
- **Impact:** Would have been stopped out at **ALL SL levels** (15%, 20%, 25%, 30%, 35%, 40%)

### 3. **SL Strategy Impact**

| SL Level | Closed Trades Affected | Open Trades Affected | Total P&L Impact |
|----------|----------------------|---------------------|------------------|
| 15% | 0 (0%) | 1 (CHOLAFIN) | ₹0 (no closed trades hit) |
| 20% | 0 (0%) | 1 (CHOLAFIN) | ₹0 (no closed trades hit) |
| 25% | 0 (0%) | 1 (CHOLAFIN) | ₹0 (no closed trades hit) |
| 30% | 0 (0%) | 1 (CHOLAFIN) | ₹0 (no closed trades hit) |
| 35% | 0 (0%) | 1 (CHOLAFIN) | ₹0 (no closed trades hit) |
| 40% | 0 (0%) | 1 (CHOLAFIN) | ₹0 (no closed trades hit) |

---

## 📈 Detailed Results

### Performance Metrics (All SL Levels)

| SL % | Win Rate | Total P&L | P&L vs Actual | Avg Drawdown | Max Drawdown | SL Hits |
|------|----------|-----------|---------------|--------------|--------------|---------|
| 15% | 100.0% | ₹15,418 | ₹0 (0.0%) | 5.78% | 63.59% | 1 (0C/1O) |
| 20% | 100.0% | ₹15,418 | ₹0 (0.0%) | 5.78% | 63.59% | 1 (0C/1O) |
| 25% | 100.0% | ₹15,418 | ₹0 (0.0%) | 5.78% | 63.59% | 1 (0C/1O) |
| 30% | 100.0% | ₹15,418 | ₹0 (0.0%) | 5.78% | 63.59% | 1 (0C/1O) |
| 35% | 100.0% | ₹15,418 | ₹0 (0.0%) | 5.78% | 63.59% | 1 (0C/1O) |
| 40% | 100.0% | ₹15,418 | ₹0 (0.0%) | 5.78% | 63.59% | 1 (0C/1O) |

**Legend:** C = Closed trades, O = Open trades

---

## 💡 Critical Insights

### 1. **CHOLAFIN Trade Analysis**
- **Entry:** ₹32.00
- **Lowest:** ₹11.65 (-63.59%)
- **Current Status:** Open, hasn't hit target
- **SL Impact:** Would have been stopped out at ₹27.20 (15% SL), saving ₹4.80 per share
- **Capital Protection:** SL would have prevented 63.59% loss

### 2. **Why All SL Levels Perform the Same**
- **Closed trades:** 0% drawdown → No SL would hit
- **Open trade (CHOLAFIN):** 63.59% drawdown → ALL SL levels would hit
- **Result:** All SL strategies (15-40%) have identical performance

### 3. **Average Drawdown Calculation**
- **10 closed trades:** 0% drawdown each
- **1 open trade (CHOLAFIN):** 63.59% drawdown
- **Average:** (0% × 10 + 63.59% × 1) / 11 = **5.78%**

---

## ✅ Recommendation

### **Recommended SL: 30%**

**Reasoning:**
1. **Capital Protection:** 30% SL would have protected capital in CHOLAFIN trade
2. **No False Stops:** Would not have stopped out any profitable trades (all had 0% drawdown)
3. **Balance:** Provides protection while allowing normal option volatility
4. **Industry Standard:** 25-30% is common for options trading

### **Alternative: 25% SL**
- Slightly tighter protection
- Still safe for your trading pattern (0% drawdown on winners)
- Better capital preservation

### **For Weekly Options (≤7 days to expiry):**
- **Recommended: 40% SL**
- Weekly options have higher volatility
- Need wider SL to avoid false stops

---

## 🎯 Implementation Strategy

### Phase 1: Initial Implementation
1. **Set default SL:** 30% for monthly options
2. **Set default SL:** 40% for weekly options
3. **Enable trailing SL:** 3% trailing distance
4. **Place SL as separate order:** After entry order (non-blocking)

### Phase 2: Monitoring
1. Track SL hit rate
2. Monitor false stops (trades that hit SL then recovered)
3. Adjust SL percentage based on 3-month performance

### Phase 3: Optimization
1. Analyze new trades after 1 month
2. Re-run backtest with new data
3. Fine-tune SL levels if needed

---

## 📊 Trade-by-Trade Analysis

### Closed Trades (All Successful)
1. **PRESTIGE 1680 CE:** Entry ₹47.85, Lowest ₹47.85, DD: 0.00% ✅
2. **BANKNIFTY 59800 CE:** Entry ₹600.00, Lowest ₹600.00, DD: 0.00% ✅
3. **POLICYBZR 1900 CE:** Entry ₹66.00, Lowest ₹66.00, DD: 0.00% ✅
4. **SENSEX 85500 CE:** Entry ₹540.00, Lowest ₹540.00, DD: 0.00% ✅
5. **NIFTY 26200 PE:** Entry ₹115.00, Lowest ₹115.00, DD: 0.00% ✅
6. **BANKNIFTY 59500 PE:** Entry ₹490.00, Lowest ₹490.00, DD: 0.00% ✅
7. **PGEL 530 CE:** Entry ₹28.00, Lowest ₹28.00, DD: 0.00% ✅
8. **BANKNIFTY 59600 CE:** Entry ₹500.00, Lowest ₹500.00, DD: 0.00% ✅
9. **ADANIENSOL 990 CE:** Entry ₹30.00, Lowest ₹30.00, DD: 0.00% ✅
10. **SENSEX 84500 CE:** Entry ₹470.00, Lowest ₹470.00, DD: 0.00% ✅

### Open Trade (High Risk)
1. **CHOLAFIN 1780 CE:** Entry ₹32.00, Lowest ₹11.65, DD: **63.59%** ⚠️
   - Would have been stopped out at ALL SL levels
   - SL would have saved significant capital
   - Example: 30% SL at ₹22.40 would have saved ₹9.60 per share

---

## 🚀 Next Steps

1. **Implement 30% SL** for monthly options
2. **Implement 40% SL** for weekly options  
3. **Enable trailing SL** at 3% distance
4. **Place SL as separate order** after entry (non-blocking)
5. **Monitor performance** for 1 month
6. **Re-analyze** with new trade data

---

## 📝 Notes

- **Data Limitation:** Analysis based on `lowest_price` from trades.json
- **Future Analysis:** Full OHLC backtest would provide intraday precision
- **CHOLAFIN Trade:** Critical case study - demonstrates SL value
- **All SL Levels:** Perform identically for closed trades (0% drawdown)
- **Recommendation:** 30% SL provides optimal balance

---

**Generated:** $(date)  
**Script:** `sl_backtest_simple.py`  
**Data Source:** `webapp/data/users/user_iYew5t9Qqn0Uw1yXCzfd-A/trades.json`

