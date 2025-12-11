# Trailing Stop Loss & Telegram Integration Guide

## 🎯 Overview

The system now includes:
1. **Trailing Stop Loss Worker** - Automatically updates SL as price moves favorably
2. **Telegram Reply Integration** - Books profits and cancels orders on Zerodha based on Telegram messages

---

## 🔄 Trailing Stop Loss Worker

### How It Works

1. **Monitors Open Positions**: Checks all open live trades every 1 minute
2. **Tracks Highest Price**: Records the highest price since entry
3. **Updates Stop Loss**: Automatically moves SL up as price moves favorably
4. **Modifies Zerodha Orders**: Updates SL order on Zerodha using `modify_order()`

### Example Flow

```
Entry: ₹100
Initial SL: ₹95
Trailing Distance: 3%

Price moves to ₹110:
→ Highest price: ₹110
→ New SL: ₹110 × (1 - 3%) = ₹106.70
→ SL order modified on Zerodha ✅

Price moves to ₹115:
→ Highest price: ₹115
→ New SL: ₹115 × (1 - 3%) = ₹111.55
→ SL order modified on Zerodha ✅

Price falls to ₹111:
→ SL at ₹111.55 triggers
→ Position closed automatically ✅
```

### Configuration

Enable trailing SL when creating a trade:

```json
{
  "trailing_enabled": true,
  "trailing_type": "percentage",
  "trailing_distance": 3.0  // 3% trailing distance
}
```

### API Endpoints

- `GET /api/trailing-sl/status` - Check if worker is running
- `POST /api/trailing-sl/start` - Start worker manually
- `POST /api/trailing-sl/stop` - Stop worker manually

---

## 📱 Telegram Reply Integration with Zerodha

### How It Works

When a Telegram reply message is received:

1. **Parse Instruction**: Detects "cancel" or "book_profits"
2. **Find Trade**: Matches reply to original trade using message ID
3. **Execute on Zerodha**: 
   - **Cancel**: Cancels pending orders on Zerodha
   - **Book Profits**: Places SELL order on Zerodha to exit position

### Cancel Order Flow

```
Telegram Reply: "Cancel the order"
    ↓
Find trade by message ID
    ↓
Check if live trade (has Zerodha orders)
    ↓
Cancel pending orders on Zerodha:
  - Buy order (if pending)
  - SL order (if pending)
  - Target order (if pending)
    ↓
Update trade status to "cancelled"
```

### Book Profits Flow

```
Telegram Reply: "Keep booking profits"
    ↓
Find trade by message ID
    ↓
Check if live trade (has Zerodha orders)
    ↓
Place SELL order on Zerodha:
  - Symbol: Same as entry
  - Quantity: Same as entry
  - Order Type: MARKET (immediate exit)
  - Exchange: NFO/BFO for options, NSE/BSE for stocks
    ↓
Update trade status to "closed"
    ↓
Calculate P&L
```

---

## 🔧 Implementation Details

### 1. Trailing Stop Loss Worker

**File**: `webapp/api/trailing_sl_worker.py`

**Features**:
- Runs every 1 minute during market hours
- Monitors all users' open live trades
- Updates SL only when price moves up (trailing up only)
- Modifies Zerodha SL orders using `modify_order()`

**Requirements**:
- Trade must have `trailing_enabled: true`
- Trade must have `zerodha_sl_order_id` (for order modification)
- Trade must be `is_live: true`

### 2. Telegram Reply Integration

**File**: `webapp/api/paper_trading.py` - `modify_trade_from_reply()`

**Cancel Order**:
- Cancels all pending Zerodha orders (buy, SL, target)
- Updates trade status to "cancelled"
- Logs cancellation reason

**Book Profits**:
- Places MARKET SELL order on Zerodha
- Calculates P&L based on current price
- Updates trade status to "closed"
- Stores exit order ID in trade data

---

## 📋 Order Modification Support

Zerodha Kite API supports order modification via `modify_order()`:

```python
client.modify_order(
    order_id="ORDER123",
    trigger_price=106.70,  # New SL price
    price=106.70,           # New SL price
    variety="regular"
)
```

**Supported Modifications**:
- ✅ Price (for LIMIT orders)
- ✅ Trigger price (for SL orders)
- ✅ Quantity
- ✅ Order type
- ✅ Validity

**Note**: Bracket orders (BO) have limited modification support. For bracket orders, you may need to cancel and recreate.

---

## 🚀 Usage Examples

### Enable Trailing SL for a Trade

When placing an order, include trailing SL settings:

```json
POST /api/orders/place
{
  "symbol": "RELIANCE",
  "transaction_type": "BUY",
  "quantity": 10,
  "price": 100.0,
  "stop_loss": 95.0,
  "target": 110.0,
  "trailing_enabled": true,
  "trailing_distance": 3.0
}
```

### Telegram Reply - Cancel Order

```
Original Signal: "Buy RELIANCE @ ₹100"
Reply: "Cancel the order"

Result:
- Pending orders cancelled on Zerodha
- Trade marked as cancelled
```

### Telegram Reply - Book Profits

```
Original Signal: "Buy RELIANCE @ ₹100"
Reply: "Keep booking profits"

Result:
- SELL order placed on Zerodha (MARKET)
- Position exited immediately
- Trade closed with P&L calculated
```

---

## ⚙️ Configuration

### Trailing SL Settings

```json
{
  "trailing_enabled": true,        // Enable trailing SL
  "trailing_type": "percentage",   // percentage, fixed, atr
  "trailing_distance": 3.0         // 3% for percentage
}
```

### Worker Settings

- **Check Interval**: 1 minute (configurable in code)
- **Market Hours**: 9:15 AM - 3:30 PM IST
- **Auto-start**: Starts automatically when webapp starts

---

## ✅ Benefits

1. **Automatic SL Management**: No manual intervention needed
2. **Protects Profits**: SL moves up as price moves favorably
3. **Telegram Integration**: Respond to signals via Telegram replies
4. **Live Trading**: Works with real Zerodha orders
5. **Capital Protection**: Prevents giving back profits

---

## 📝 Summary

✅ **Trailing SL Worker**: Automatically updates SL as price moves up
✅ **Telegram Integration**: Cancel orders and book profits via Telegram
✅ **Zerodha Integration**: All actions executed on Zerodha
✅ **Order Modification**: Updates SL orders using Zerodha API
✅ **Automatic**: Workers run in background, no manual intervention

**Your trading system is now fully automated!** 🚀


