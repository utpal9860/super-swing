# Order Monitor Worker - Momentum Loss Protection

## 🎯 Overview

The **Order Monitor Worker** is a background service that automatically monitors pending LIMIT orders and cancels them if momentum is lost. This protects your capital by preventing entries on falling prices.

---

## 🔄 How It Works

### Scenario: Order Placed, Price Moved, Then Came Back

1. **Order Placed**: LIMIT order at ₹102 (adaptive midpoint)
2. **Price Moves Up**: Reaches ₹110 (target) without filling order
3. **Price Falls Back**: Comes back to ₹102 (order price)
4. **Worker Detects**: Momentum lost - price already moved favorably
5. **Action**: **Order automatically cancelled** ✅

### Detection Logic

The worker checks every **2 minutes** during market hours:

1. **Get Pending Orders**: Finds all orders with status "PLACED"
2. **Check Zerodha Status**: Verifies order is still pending
3. **Get Current Price & High**: Fetches today's high and current price
4. **Calculate Movement**: 
   - How much price moved towards target (from order price)
   - How much price moved from today's high to current
5. **Detect Momentum Loss**:
   - If price moved >30% towards target
   - AND price is back near order price (within 1%)
   - AND price fell >3% from high
   - → **CANCEL ORDER**

---

## ⚙️ Configuration

### Automatic Startup

The worker **automatically starts** when the webapp starts:
- Runs in background
- Checks every 2 minutes during market hours (9:15 AM - 3:30 PM IST)
- Stops checking when market closes

### Manual Control

You can control the worker via API:

**Check Status:**
```bash
GET /api/order-monitor/status
```

**Start Worker:**
```bash
POST /api/order-monitor/start
```

**Stop Worker:**
```bash
POST /api/order-monitor/stop
```

---

## 📊 Example Scenarios

### Scenario 1: Momentum Lost (Order Cancelled)

```
Order Details:
- Symbol: RELIANCE
- Order Price: ₹102 (LIMIT)
- Target: ₹110
- Order Status: PLACED (pending)

Price Action:
- Today's High: ₹108 (moved 5.9% from ₹102)
- Current Price: ₹102.5 (back near order price)
- Movement from High: -5.1% (fell from ₹108)

Worker Detection:
✅ Price moved 5.9% towards target (30% threshold = 2.4%)
✅ Price is back near order price (within 1%)
✅ Price fell 5.1% from high (>3% threshold)

Action: ORDER CANCELLED
Reason: "Momentum lost - price moved up 5.9% then fell back"
```

### Scenario 2: Fresh Setup (Order Kept)

```
Order Details:
- Symbol: RELIANCE
- Order Price: ₹102 (LIMIT)
- Target: ₹110
- Order Status: PLACED (pending)

Price Action:
- Today's High: ₹103 (moved 1% from ₹102)
- Current Price: ₹102.2
- Movement from High: -0.8%

Worker Detection:
❌ Price only moved 1% (below 30% threshold of 2.4%)
→ No momentum loss detected

Action: ORDER KEPT (still valid)
```

### Scenario 3: Order Filled (No Action)

```
Order Details:
- Symbol: RELIANCE
- Order Price: ₹102 (LIMIT)
- Order Status: COMPLETE (filled)

Worker Detection:
✅ Order already filled
→ No action needed, skip check
```

---

## 🛡️ Protection Features

### 1. **Momentum Loss Detection**

Prevents entering when:
- Price already moved favorably (towards target)
- Price is now falling back
- Setup has changed (momentum lost)

### 2. **Market Hours Only**

- Only runs during market hours (9:15 AM - 3:30 PM IST)
- Waits 30 minutes when market is closed
- Prevents unnecessary API calls

### 3. **Error Handling**

- Continues monitoring even if one order check fails
- Logs all errors for debugging
- Updates order status even if cancellation fails

### 4. **Status Updates**

- Updates order status in database
- Logs cancellation reason
- Tracks all actions for audit

---

## 📋 Order Status Flow

```
PLACED (pending)
    ↓
Worker checks every 2 min
    ↓
┌─────────────────────────┐
│ Momentum Lost?          │
├─────────────────────────┤
│ YES → CANCELLED         │
│ NO  → Keep checking     │
│ Filled → COMPLETE       │
└─────────────────────────┘
```

---

## 🔍 Monitoring & Logs

### Log Messages

**Worker Started:**
```
🔄 Order Monitor Worker started
```

**Checking Orders:**
```
Checking 3 pending orders for momentum loss...
```

**Momentum Lost:**
```
🚨 MOMENTUM LOST: Order ORD123 (RELIANCE) - 
Price moved up +5.9% (reached ₹108.00) but now back to ₹102.50 
(near order price ₹102.00). Cancelling order to prevent entering on falling price.
✅ Order ORD123 cancelled successfully
```

**Order Kept:**
```
Order ORD123 (RELIANCE) - No momentum loss detected. 
Current: ₹102.20, Order: ₹102.00, High: ₹103.00
```

### Database Updates

When order is cancelled:
- `status` → `"CANCELLED"`
- `status_message` → Reason for cancellation
- `completed_at` → Timestamp

---

## ⚠️ Important Notes

1. **Only LIMIT Orders**: Worker only monitors LIMIT orders (MARKET orders execute immediately)

2. **Requires Target**: Worker needs target price to calculate momentum (uses 10% default if not provided)

3. **2-Minute Interval**: Checks every 2 minutes (configurable in code)

4. **Market Hours**: Only runs during market hours (9:15 AM - 3:30 PM IST)

5. **Zerodha Connection**: Requires active Zerodha connection for each user

---

## 🚀 Benefits

✅ **Capital Protection**: Prevents bad entries on falling prices
✅ **Automatic**: No manual intervention needed
✅ **Real-time**: Checks every 2 minutes
✅ **Smart Detection**: Only cancels when momentum is truly lost
✅ **Transparent**: All actions logged and tracked

---

## 📝 Summary

The Order Monitor Worker is your **automatic safety net** that:
- Monitors pending LIMIT orders
- Detects momentum loss
- Cancels orders before they execute on falling prices
- Protects your capital automatically

**Set it and forget it!** The worker runs automatically and protects your trades. 🛡️


