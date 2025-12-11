# Live Trading Implementation - Options Support

## ✅ Implementation Complete

All critical fixes for options trading with Zerodha Kite API have been implemented.

---

## 🔧 Changes Made

### 1. **Option Detection** (`webapp/order_manager.py`)

Added `is_option_symbol()` function to detect if a symbol is an option:
- Checks if symbol ends with "CE" or "PE"
- Handles `.NS` suffix removal

### 2. **Exchange Selection** (`webapp/order_manager.py`)

Added `get_option_exchange()` function:
- **BSE indices** (SENSEX, BANKEX, SENSEX50) → `"BFO"`
- **NSE indices/stocks** → `"NFO"`
- Automatically selected when placing option orders

### 3. **Product Type Selection** (`webapp/order_manager.py`)

Added product type functions:
- `get_product_type_for_option()` → `"NRML"` (Normal - allows holding until expiry)
- `get_product_type_for_stock()` → `"CNC"` (Cash and Carry - delivery)
- Automatically selected based on option vs stock

### 4. **Quantity Calculation** (`webapp/order_manager.py`)

Added `calculate_option_quantity()`:
- For options: `quantity = shares × lot_size`
- For stocks: `quantity = shares` (as-is)
- Automatically applied in `prepare_order_params()`

### 5. **Underlying Symbol Extraction** (`webapp/order_manager.py`)

Added `extract_underlying_from_option_symbol()`:
- Extracts underlying from option symbols like:
  - `SENSEX11DEC84500CE` → `SENSEX`
  - `PRESTIGE25DEC1680CE` → `PRESTIGE`
- Handles both index and stock options
- Used to lookup lot sizes

### 6. **Enhanced Order Parameter Preparation** (`webapp/order_manager.py`)

Updated `prepare_order_params()` to:
- Auto-detect if symbol is an option
- Auto-select exchange (NFO/BFO for options, NSE/BSE for stocks)
- Auto-select product (NRML for options, CNC for stocks)
- Auto-calculate quantity (lots × lot_size for options)
- Accept optional `is_option` and `lot_size` parameters

### 7. **Symbol Resolution** (`webapp/zerodha_client.py`)

Added `resolve_option_symbol()` method:
- Constructs option symbol using our format
- Fetches Zerodha instrument list for NFO/BFO
- Matches our symbol to Zerodha's exact format
- Handles exact match, case-insensitive match, and partial match
- Returns Zerodha's exact trading symbol

### 8. **Order API Integration** (`webapp/api/orders_api.py`)

Updated `place_order()` endpoint to:
- Detect if order is for an option
- Extract underlying symbol from option symbol
- Get lot size for the underlying
- Use enhanced `prepare_order_params()` with option handling
- Automatically set correct exchange and product

---

## 📋 How It Works

### For Options Orders:

1. **Symbol Detection**: Checks if symbol ends with "CE" or "PE"
2. **Underlying Extraction**: Extracts underlying (e.g., "SENSEX" from "SENSEX11DEC84500CE")
3. **Lot Size Lookup**: Gets lot size for underlying (e.g., SENSEX = 10)
4. **Exchange Selection**: 
   - BSE indices → `BFO`
   - NSE indices/stocks → `NFO`
5. **Product Selection**: `NRML` (allows holding until expiry)
6. **Quantity Calculation**: `shares × lot_size` (e.g., 1 lot × 10 = 10 contracts)
7. **Order Placement**: Places order with correct parameters

### For Stock Orders:

1. **Symbol Detection**: Not an option
2. **Exchange**: Uses provided exchange (NSE/BSE) or defaults to NSE
3. **Product**: `CNC` (Cash and Carry - delivery)
4. **Quantity**: Uses quantity as-is (no lot size multiplication)
5. **Order Placement**: Places order with correct parameters

---

## 🧪 Testing Checklist

Before going live, test:

- [ ] **NSE Index Options** (NIFTY, BANKNIFTY)
  - [ ] Symbol detection works
  - [ ] Exchange set to `NFO`
  - [ ] Product set to `NRML`
  - [ ] Quantity calculated correctly (lots × lot_size)
  - [ ] Order placed successfully

- [ ] **BSE Index Options** (SENSEX)
  - [ ] Symbol detection works
  - [ ] Exchange set to `BFO`
  - [ ] Product set to `NRML`
  - [ ] Quantity calculated correctly (lots × lot_size)
  - [ ] Order placed successfully

- [ ] **Stock Options** (PRESTIGE, CHOLAFIN)
  - [ ] Symbol detection works
  - [ ] Exchange set to `NFO`
  - [ ] Product set to `NRML`
  - [ ] Quantity calculated correctly (lots × lot_size)
  - [ ] Order placed successfully

- [ ] **Stock Delivery Orders**
  - [ ] Not detected as option
  - [ ] Exchange set to `NSE` or `BSE`
  - [ ] Product set to `CNC`
  - [ ] Quantity used as-is
  - [ ] Order placed successfully

---

## ⚠️ Important Notes

### Symbol Format

The system expects option symbols in the format:
- **Weekly contracts**: `SENSEX11DEC84500CE` (DD + MON + STRIKE + TYPE)
- **Monthly contracts**: `PRESTIGE25DEC1680CE` (YY + MON + STRIKE + TYPE)

If your symbols are in a different format, the `resolve_option_symbol()` method will try to match them to Zerodha's format.

### Lot Size

Lot sizes are fetched from `webapp/data/lot_sizes.json`. Make sure this file is up-to-date with current lot sizes.

### Symbol Resolution

The `resolve_option_symbol()` method is available but not automatically called in the order placement flow. To use it:

```python
# In orders_api.py, after getting client:
if is_option:
    # Extract strike, expiry, option_type from symbol or trade data
    resolved_symbol = client.resolve_option_symbol(
        symbol=underlying_symbol,
        strike=strike,
        option_type=option_type,
        expiry_date_str=expiry_date_str
    )
    if resolved_symbol:
        order_params['symbol'] = resolved_symbol
```

### Error Handling

- If lot size cannot be determined, defaults to 1
- If underlying cannot be extracted, logs warning and continues
- If symbol resolution fails, uses original symbol (Zerodha will validate)

---

## 🚀 Next Steps

1. **Test with Paper Trading**: Test all scenarios with small quantities
2. **Verify Symbol Formats**: Ensure your option symbols match Zerodha's format
3. **Update Lot Sizes**: Keep `lot_sizes.json` updated
4. **Enable Symbol Resolution**: Optionally enable automatic symbol resolution
5. **Monitor Orders**: Watch for any rejections and adjust as needed

---

## 📝 Example Usage

### Placing an Option Order:

```python
order_data = OrderRequest(
    symbol="SENSEX11DEC84500CE",  # Option symbol
    exchange="BFO",  # Will be auto-corrected if wrong
    transaction_type="BUY",
    quantity=1,  # 1 lot
    order_type="MARKET",
    product="NRML"  # Will be auto-set to NRML for options
)

# System will:
# 1. Detect it's an option
# 2. Extract underlying: "SENSEX"
# 3. Get lot size: 10
# 4. Calculate quantity: 1 × 10 = 10 contracts
# 5. Set exchange: "BFO"
# 6. Set product: "NRML"
# 7. Place order
```

### Placing a Stock Order:

```python
order_data = OrderRequest(
    symbol="RELIANCE",
    exchange="NSE",
    transaction_type="BUY",
    quantity=10,  # 10 shares
    order_type="MARKET",
    product="CNC"  # Delivery
)

# System will:
# 1. Detect it's not an option
# 2. Use exchange as-is: "NSE"
# 3. Use product as-is: "CNC"
# 4. Use quantity as-is: 10
# 5. Place order
```

---

## ✅ Status: READY FOR TESTING

All core functionality is implemented. Test thoroughly before going live!

