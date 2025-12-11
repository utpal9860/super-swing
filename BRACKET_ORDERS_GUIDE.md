# Fire-and-Forget Bracket Orders Guide

## 🎯 Overview

The system now supports **fire-and-forget bracket orders** that automatically:
1. Place entry order (can be above/below market for breakout)
2. Place stop loss order (auto-exit if price falls)
3. Place target order (auto-exit if price rises)
4. Automatically cancel the other order when one hits

**No manual intervention needed!** Once placed, the orders manage themselves.

---

## 🔥 How Bracket Orders Work

### Automatic Behavior:

1. **Entry Order Placed**: Your entry order is placed (LIMIT or MARKET)
2. **SL & Target Queued**: Stop Loss and Target orders are queued (not active yet)
3. **Entry Fills**: When entry order executes, SL and Target become active
4. **Auto-Exit**: When either SL or Target hits, the other is automatically cancelled
5. **Position Closed**: Your position is automatically closed

### Example Flow:

```
1. Place bracket order:
   - Entry: BUY 10 shares @ ₹100 (LIMIT)
   - SL: SELL 10 shares @ ₹95
   - Target: SELL 10 shares @ ₹110

2. Entry order executes at ₹100
   → SL and Target orders become active

3. Price moves to ₹110
   → Target order executes
   → SL order automatically cancelled
   → Position closed with profit ✅

OR

3. Price moves to ₹95
   → SL order executes
   → Target order automatically cancelled
   → Position closed with loss ✅
```

---

## 📋 Order Types

### 1. **Bracket Order (Fire-and-Forget)** - RECOMMENDED

**When to use**: When you have both SL and Target

**How it works**:
- All 3 orders placed together
- Entry fills → SL and Target activate
- One hits → Other cancels automatically

**Request**:
```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "transaction_type": "BUY",
  "quantity": 10,
  "order_type": "LIMIT",
  "price": 100.0,  // Entry price (can be above/below market)
  "stop_loss": 95.0,  // Required for bracket order
  "target": 110.0,  // Required for bracket order
  "product": "CNC"
}
```

**Response**:
```json
{
  "success": true,
  "order_id": "ORD123",
  "order_type": "bracket",
  "message": "Bracket order placed successfully (fire-and-forget with auto SL and Target)",
  "stop_loss": 95.0,
  "target": 110.0,
  "note": "Entry, SL, and Target orders are all active. When entry fills, SL and Target become active. When either hits, the other is automatically cancelled."
}
```

### 2. **Regular Order** (No Auto-Exit)

**When to use**: When you don't have SL/Target or want manual control

**Request**:
```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "transaction_type": "BUY",
  "quantity": 10,
  "order_type": "LIMIT",
  "price": 100.0
  // No stop_loss or target
}
```

---

## 🎯 Breakout Orders (Above/Below Market)

### Scenario: Price Waiting for Breakout

You want to buy when price breaks above ₹105 (currently at ₹100):

```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "transaction_type": "BUY",
  "quantity": 10,
  "order_type": "LIMIT",
  "price": 105.0,  // Above current market price
  "stop_loss": 100.0,
  "target": 115.0
}
```

**What happens**:
- Entry order placed at ₹105 (above current price)
- If price breaks above ₹105 → Entry executes
- SL and Target activate automatically
- Fire-and-forget from here!

### Scenario: Price Waiting for Support

You want to buy when price falls to support at ₹95 (currently at ₹100):

```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "transaction_type": "BUY",
  "quantity": 10,
  "order_type": "LIMIT",
  "price": 95.0,  // Below current market price
  "stop_loss": 90.0,
  "target": 105.0
}
```

**What happens**:
- Entry order placed at ₹95 (below current price)
- If price falls to ₹95 → Entry executes
- SL and Target activate automatically
- Fire-and-forget from here!

---

## ⚙️ Options Trading

Bracket orders work for options too! The system automatically:
- Detects if it's an option
- Sets correct exchange (NFO/BFO)
- Sets correct product (NRML)
- Calculates quantity (lots × lot_size)

**Example**:
```json
{
  "symbol": "SENSEX11DEC84500CE",
  "exchange": "BFO",  // Auto-corrected if wrong
  "transaction_type": "BUY",
  "quantity": 1,  // 1 lot
  "order_type": "LIMIT",
  "price": 470.0,
  "stop_loss": 450.0,
  "target": 520.0,
  "product": "NRML"  // Auto-set for options
}
```

**System automatically**:
- Detects it's an option
- Extracts underlying: "SENSEX"
- Gets lot size: 10
- Calculates quantity: 1 × 10 = 10 contracts
- Sets exchange: "BFO"
- Sets product: "NRML"
- Places bracket order with 10 contracts

---

## 🚨 Important Notes

### 1. **Product Type for Options**

- **Options**: Must use `"NRML"` (Normal - allows holding until expiry)
- **Stocks**: Can use `"CNC"` (delivery) or `"MIS"` (intraday)

The system auto-sets this, but you can override.

### 2. **Bracket Orders vs Regular Orders**

- **Bracket Order**: Requires both `stop_loss` AND `target`
- **Regular Order**: Can have neither, one, or both (but won't auto-exit)

### 3. **Order Execution**

- Entry order must fill first
- SL and Target activate only after entry fills
- If entry doesn't fill, SL and Target remain queued

### 4. **Market Orders**

For immediate execution, use `"order_type": "MARKET"`:

```json
{
  "order_type": "MARKET",  // Executes immediately at market price
  "price": null,  // Not needed for market orders
  "stop_loss": 95.0,
  "target": 110.0
}
```

---

## 📊 API Endpoints

### 1. Place Order (Auto-Bracket if SL + Target provided)

**Endpoint**: `POST /api/orders/place`

**Request**:
```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "transaction_type": "BUY",
  "quantity": 10,
  "order_type": "LIMIT",
  "price": 100.0,
  "stop_loss": 95.0,
  "target": 110.0,
  "product": "CNC"
}
```

**Response**:
```json
{
  "success": true,
  "order_id": "ORD123",
  "order_type": "bracket",
  "zerodha_order_id": "ZER123",
  "message": "Bracket order placed successfully (fire-and-forget with auto SL and Target)",
  "stop_loss": 95.0,
  "target": 110.0
}
```

### 2. Place Bracket Order (Explicit)

**Endpoint**: `POST /api/orders/place-bracket`

Same as above, but explicitly creates bracket order.

---

## ✅ Benefits

1. **Fire-and-Forget**: Place once, manage automatically
2. **No Manual Intervention**: SL and Target execute automatically
3. **Breakout Support**: Can place orders above/below market
4. **Options Support**: Works for both stocks and options
5. **Auto-Exit**: Position closes automatically when target or SL hits

---

## 🧪 Testing

Before going live, test:

1. **Breakout Above Market**:
   - Place LIMIT order above current price
   - Verify order is queued
   - When price breaks → Entry executes → SL/Target activate

2. **Breakout Below Market**:
   - Place LIMIT order below current price
   - Verify order is queued
   - When price falls → Entry executes → SL/Target activate

3. **Market Order**:
   - Place MARKET order with SL/Target
   - Verify entry executes immediately
   - Verify SL/Target activate

4. **Options Bracket Order**:
   - Place option order with SL/Target
   - Verify exchange/product/quantity are correct
   - Verify bracket order is created

---

## 🎯 Best Practices

1. **Always Use Bracket Orders**: When you have SL and Target, use bracket orders
2. **Set Realistic Prices**: Entry price should be achievable
3. **Check Market Hours**: Orders placed outside market hours will queue
4. **Monitor Entry**: If entry doesn't fill, SL/Target won't activate
5. **Test First**: Test with small quantities before scaling

---

## 📝 Summary

✅ **Bracket orders are now the default** when SL and Target are provided
✅ **Fire-and-forget**: No manual intervention needed
✅ **Breakout support**: Can place orders above/below market
✅ **Options support**: Works for both stocks and options
✅ **Auto-exit**: Position closes automatically

**You're ready for fire-and-forget trading!** 🚀


