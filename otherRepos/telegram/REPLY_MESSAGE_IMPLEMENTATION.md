# Implementation: Telegram Reply Message Handling

## Summary
Successfully implemented handling of Telegram reply messages that modify trades. The system now:
- Detects when a message is a reply to a signal
- Parses reply messages for instructions ("cancel", "book profits")
- Matches replies to their original trades using message IDs
- Executes trade modifications (cancel or exit at current price)

## Files Created/Modified

### New Files
1. **`otherRepos/telegram/reply_parser.py`**
   - Parses reply messages for trade modification instructions
   - Detects keywords: "cancel", "book profits", "scalping profits", etc.
   - Returns action dict: `{"action": "cancel"}` or `{"action": "book_profits"}`

2. **`otherRepos/telegram/REPLY_MESSAGE_PLAN.md`**
   - Detailed implementation plan and architecture

### Modified Files

1. **`webapp/api/paper_trading.py`**
   - Added `telegram_message_id`, `telegram_channel_id`, `telegram_channel_name` to `Trade` model
   - Added these fields to `SignalOrder` model
   - Store message IDs when creating trades from signals
   - New endpoint: `GET /api/trades/find_by_message_id` - Find trade by Telegram message ID
   - New endpoint: `POST /api/trades/modify_from_reply` - Modify trade based on reply instruction
     - Supports "cancel" and "book_profits" actions
     - "cancel": Closes trade with exit_reason="cancelled"
     - "book_profits": Exits trade at current LTP

2. **`otherRepos/telegram/message_handler.py`**
   - Updated `extract_message_data()` to extract reply information
   - Adds `is_reply` and `reply_to_msg_id` to message data

3. **`otherRepos/telegram/orchestrator.py`**
   - Import `reply_parser` module
   - Check for reply messages before parsing signals
   - Parse reply instructions and forward to webapp API
   - Pass `telegram_message_id`, `telegram_channel_id`, `telegram_channel_name` when creating trades

## How It Works

### Flow Diagram
```
Telegram Message Received
    ↓
Is it a reply? (message.reply_to exists)
    ↓ YES
Parse reply text for instructions
    ↓
Instruction found? (cancel/book_profits)
    ↓ YES
POST /api/trades/modify_from_reply
    ↓
Find trade by message_id + channel_id
    ↓
Execute instruction:
  - cancel → Close trade as cancelled
  - book_profits → Exit at current LTP
    ↓
Trade modified ✅
```

### Signal Creation Flow
```
Telegram Signal Received
    ↓
Parse signal (BUY ASHOKLEY 163 CE...)
    ↓
POST /api/trades/create_from_signal
    ↓
Store trade with:
  - telegram_message_id
  - telegram_channel_id
  - telegram_channel_name
    ↓
Trade created ✅
```

## API Endpoints

### 1. Find Trade by Message ID
```
GET /api/trades/find_by_message_id?message_id=123&channel_id=456
```
Returns the open trade associated with the Telegram message ID.

### 2. Modify Trade from Reply
```
POST /api/trades/modify_from_reply
Body: {
    "message_id": 123,
    "channel_id": 456,
    "instruction": "cancel" | "book_profits"
}
```
Modifies the trade based on the reply instruction.

## Supported Instructions

### Cancel
**Keywords**: cancel, cancelled, cancel order, don't take, skip, ignore, no entry, don't enter

**Action**: Closes the trade with:
- `exit_reason = "cancelled"`
- `exit_price = entry_price` (no price change)
- `net_pnl = 0` (no brokerage charged)

### Book Profits
**Keywords**: book profits, booking profits, scalping profits, keep booking, keep scalping, exit now, square off, close position, take profit, book and exit

**Action**: Exits the trade immediately:
- Fetches current LTP for options
- Closes trade at current price
- Calculates P&L with brokerage
- `exit_reason = "book_profits"`

## Testing

### Manual Testing Steps
1. **Create a trade from signal**:
   - Monitor Telegram channel
   - Signal received: "BUY ASHOKLEY 163 CE ABOVE 3.75"
   - Verify trade created with `telegram_message_id` stored

2. **Test cancel instruction**:
   - Reply to signal: "Cancel the order"
   - Verify trade is closed with `exit_reason="cancelled"`

3. **Test book profits instruction**:
   - Reply to signal: "Keep booking profits"
   - Verify trade is closed at current LTP with `exit_reason="book_profits"`

### Expected Console Output
```
[SIGNAL] ASHOKLEY 163 CE ABOVE 3.75 | LTP: 3.80
[REPLY-MODIFY] CANCEL -> 200 | Reply to msg 12345
[REPLY-MODIFY] ✅ Successfully cancel trade for message 12345
```

## Edge Cases Handled

1. **Multiple trades from same signal**: Returns most recent open trade
2. **Trade already closed**: Returns 404 error
3. **Message ID not found**: Returns 404 error
4. **Ambiguous instructions**: Cancel checked first (more specific), then book_profits
5. **LTP unavailable for book_profits**: Falls back to entry price (logs warning)

## Future Enhancements

1. **Zerodha Integration**: Cancel pending orders when "cancel" instruction received
2. **SL Movement**: Instead of exiting, move SL to current price for "book profits"
3. **Partial Exit**: Support partial position closing
4. **Signal Details Matching**: Fallback to match by symbol/strike/option_type if message ID not found
5. **Confidence Levels**: Track signal confidence and auto-exit low confidence signals

## Notes

- Reply messages are processed **before** signal parsing
- Both reply handling and signal creation can happen in the same message handler
- Message IDs are stored per user, so multi-user support is maintained
- The system works for both paper trading and can be extended for live trading


