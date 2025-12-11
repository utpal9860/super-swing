# Adaptive Order Strategy - Pro Trader Approach

## 🎯 Problem Statement

**Scenario 1**: Signal comes in at ₹95, but by the time order is placed, price is ₹100.
**Question**: Should we enter at ₹100 (risk too much) or wait for ₹95 (might miss trade)?

**Scenario 2**: Entry order placed at ₹95, price moves to ₹100 (target), then comes back to ₹95.
**Question**: Should we enter now at ₹95 (price is falling, momentum lost)?

**Answer**: **Adaptive Strategy** - Smart decision based on price movement AND momentum detection!

---

## 🧠 Pro Trader Strategy

### Price Movement Analysis:

1. **Price moved <2%**: Use original price (LIMIT) - wait for pullback
2. **Price moved 2-5%**: Use adaptive price (LIMIT at midpoint or current)
3. **Price moved >5%**: Reject order (too risky)
4. **Price already moved favorably then came back**: Reject order (momentum lost)

---

## 📊 Decision Matrix

| Price Movement | Strategy | Order Type | Price Used | Action |
|---------------|----------|------------|------------|--------|
| **<2%** | Original Price | LIMIT | Signal Price (₹95) | Wait for pullback |
| **2-5% UP** | Adaptive Midpoint | LIMIT | Midpoint (₹97.50) | Balance entry & risk |
| **2-5% DOWN** | Adaptive Current | LIMIT | Current (₹93) | Better entry |
| **>5%** | Reject | - | - | **REJECT** (too risky) |
| **Moved favorably then back** | Reject | - | - | **REJECT** (momentum lost) |

---

## 🔧 How It Works

### 1. **Price Movement Detection**

```python
# System automatically:
1. Gets current market price from Zerodha
2. Compares with signal price
3. Calculates movement percentage
4. Applies adaptive strategy
```

### 2. **Example Scenarios**

#### Scenario A: Price Moved Up 1% (₹95 → ₹96.05)
```
Signal Price: ₹95
Current Price: ₹96.05
Movement: +1.08%

Strategy: Original Price
Order Type: LIMIT
Price: ₹95 (wait for pullback)
Result: Order placed at ₹95, will execute when price comes back
```

#### Scenario B: Price Moved Up 3% (₹95 → ₹97.85)
```
Signal Price: ₹95
Current Price: ₹97.85
Movement: +3.0%

Strategy: Adaptive Midpoint
Order Type: LIMIT
Price: ₹96.43 (midpoint)
Result: Compromise - better than ₹97.85, but won't wait for ₹95
```

#### Scenario C: Price Moved Up 6% (₹95 → ₹100.70)
```
Signal Price: ₹95
Current Price: ₹100.70
Movement: +6.0%

Strategy: REJECT
Result: Order rejected - price moved too much, too risky
Message: "Price moved +6.0%. Movement exceeds maximum tolerance (5%). Order rejected."
```

#### Scenario D: Price Moved Favorably Then Came Back (Momentum Lost)
```
Signal Price: ₹95
Target: ₹110
Current Price: ₹96 (near entry)
Today's High: ₹105 (moved 10.5% towards target, then fell back)

Strategy: REJECT (Momentum Lost)
Result: Order rejected - price already moved favorably, now falling
Message: "Price already moved up +10.5% (reached ₹105) towards target ₹110, 
         but now back to ₹96 (near entry ₹95). Momentum lost - order rejected 
         to prevent entering on falling price."
```

**Why Reject?**
- Price already showed it can move towards target (₹105 from ₹95)
- But now it's falling back (₹105 → ₹96)
- Entering now = entering on falling price = bad momentum
- Better to wait for fresh setup or reject the trade

---

## ⚙️ Configuration

### Default Settings:

```json
{
  "price_tolerance_pct": 2.0,      // Acceptable movement (2%)
  "max_price_movement_pct": 5.0,    // Maximum movement (5%)
  "is_breakout": false              // Breakout signal flag
}
```

### Customizable Per Order:

```json
{
  "symbol": "RELIANCE",
  "price": 95.0,
  "signal_price": 95.0,              // Original signal price
  "price_tolerance_pct": 2.0,        // Custom tolerance
  "max_price_movement_pct": 5.0,     // Custom max movement
  "is_breakout": false                // Set true for breakout signals
}
```

---

## 📋 API Usage

### Example 1: Regular Order (Auto-Adaptive)

```json
POST /api/orders/place
{
  "symbol": "RELIANCE",
  "transaction_type": "BUY",
  "quantity": 10,
  "order_type": "LIMIT",
  "price": 95.0,
  "signal_price": 95.0,  // Original signal price
  "stop_loss": 90.0,
  "target": 110.0
}
```

**What happens**:
1. System gets current price (e.g., ₹97)
2. Calculates movement: +2.1%
3. Applies adaptive strategy: Uses midpoint ₹96
4. Places bracket order at ₹96 with SL and Target

### Example 2: High Movement (Auto-Reject)

```json
{
  "symbol": "RELIANCE",
  "price": 95.0,
  "signal_price": 95.0,
  "max_price_movement_pct": 5.0
}
```

**If current price is ₹101 (6% movement)**:
- Order is **REJECTED**
- Returns error: "Price moved +6.0%. Movement exceeds maximum tolerance (5%). Order rejected."

---

## ✅ Benefits

1. **Prevents Bad Entries**: Rejects orders when price moved too much
2. **Balances Risk**: Uses adaptive pricing for moderate movements
3. **Won't Miss Trades**: Uses MARKET for breakouts
4. **Smart Waiting**: Waits for pullback when movement is small
5. **Transparent**: Logs all decisions and warnings

---

## 🎯 Best Practices

### 1. **Set Realistic Tolerances**

- **Conservative**: `price_tolerance_pct: 1.0`, `max_price_movement_pct: 3.0`
- **Moderate**: `price_tolerance_pct: 2.0`, `max_price_movement_pct: 5.0` (default)
- **Aggressive**: `price_tolerance_pct: 3.0`, `max_price_movement_pct: 7.0`

### 2. **Monitor Warnings**

Check the `warning` field in response:
- Tells you what strategy was used
- Explains price movement
- Helps you understand the decision

### 3. **Adjust Based on Volatility**

- **High volatility stocks**: Increase tolerance (3-5%)
- **Low volatility stocks**: Decrease tolerance (1-2%)
- **Options**: Usually higher tolerance (3-7%)

---

## 📊 Response Format

### Success Response:

```json
{
  "success": true,
  "order_id": "ORD123",
  "zerodha_order_id": "ZER123",
  "order_strategy": {
    "final_order_type": "LIMIT",
    "final_price": 96.43,
    "signal_price": 95.0,
    "current_price": 97.85
  },
  "warning": "Price moved up +3.0% (signal: ₹95.00, current: ₹97.85). Using adaptive LIMIT at ₹96.43 (midpoint) to balance entry and risk.",
  "order_type": "bracket",
  "stop_loss": 90.0,
  "target": 110.0
}
```

### Rejection Response:

```json
{
  "success": false,
  "detail": "Price moved +6.0% (signal: ₹95.00, current: ₹100.70). Movement exceeds maximum tolerance (5%). Order rejected to prevent high-risk entry."
}
```

---

## 🚨 Important Notes

1. **Signal Price Required**: Always provide `signal_price` for adaptive strategy
2. **Current Price Fetch**: System automatically fetches current price from Zerodha
3. **Rejection Safety**: Orders rejected when price moved >5% (configurable)
4. **Transparency**: All decisions are logged and returned in response

---

## 💡 Pro Trader Tips

1. **For Pullback Trades**: Use LIMIT with original price (system will wait)
2. **For Volatile Stocks**: Increase `max_price_movement_pct` to 7-10%
3. **For Stable Stocks**: Decrease to 3-4%
4. **Monitor Warnings**: Check warnings to understand system decisions
5. **Set Signal Price**: Always provide `signal_price` to enable adaptive strategy

---

## 📝 Summary

✅ **Adaptive Strategy**: Automatically adjusts based on price movement
✅ **Risk Management**: Rejects orders when price moved too much
✅ **Smart Execution**: Uses best order type and price
✅ **Transparent**: All decisions logged and explained

**You now have a pro trader's order execution system!** 🚀

