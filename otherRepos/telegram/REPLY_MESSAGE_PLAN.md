# Plan: Handle Telegram Reply Messages for Trade Modifications

## Overview
Telegram signals often include follow-up messages that reply to the original signal. These replies contain instructions like:
- "Cancel the order" (when order doesn't trigger)
- "Keep booking profits" or "Keep scalping profits" (low confidence signals - exit immediately or move SL to current price)

## Research Findings

### Telethon Reply Message API
In Telethon, `event.message.reply_to` contains information about the replied message:
- `event.message.reply_to.reply_to_msg_id` - The message ID being replied to
- `event.message.reply_to` is `None` if the message is not a reply

### Current Architecture
1. **Signal Processing**: `orchestrator.py` handles new messages via `events.NewMessage`
2. **Signal Parsing**: `signal_parser.py` parses structured signals (BUY/SELL format)
3. **Trade Creation**: `webapp/api/paper_trading.py` creates trades via `/api/trades/create_from_signal`
4. **Trade Storage**: Trades stored in JSON files with user-specific paths

## Implementation Plan

### Phase 1: Store Message IDs with Trades
**Goal**: Link trades to their originating Telegram messages

**Changes Required**:
1. **Trade Model** (`webapp/api/paper_trading.py`):
   - Add field: `telegram_message_id: Optional[int] = None`
   - Add field: `telegram_channel_id: Optional[int] = None`
   - Add field: `telegram_channel_name: Optional[str] = None`

2. **Signal Creation** (`webapp/api/paper_trading.py`):
   - Modify `SignalOrder` model to accept optional `telegram_message_id`, `telegram_channel_id`, `telegram_channel_name`
   - Store these fields when creating trade from signal

3. **Orchestrator** (`otherRepos/telegram/orchestrator.py`):
   - Pass `message.id`, `event.chat_id`, and `channel_name` in payload to webapp API

### Phase 2: Detect and Parse Reply Messages
**Goal**: Identify reply messages and extract instructions

**Changes Required**:
1. **Reply Message Parser** (`otherRepos/telegram/reply_parser.py` - NEW FILE):
   ```python
   def parse_reply_instruction(message_text: str) -> Optional[Dict]:
       """
       Parse reply message for trade modification instructions.
       
       Returns:
       - {"action": "cancel"} for cancel instructions
       - {"action": "book_profits"} for book profits/scalping instructions
       - None if not a modification instruction
       """
   ```
   
   **Keywords to detect**:
   - Cancel: "cancel", "cancelled", "cancel order", "don't take", "skip"
   - Book Profits: "book profits", "booking profits", "scalping profits", "keep booking", "keep scalping", "exit", "square off"

2. **Orchestrator Handler** (`otherRepos/telegram/orchestrator.py`):
   - Check if `event.message.reply_to` exists
   - If yes, extract `reply_to_msg_id`
   - Parse reply message text for instructions
   - If instruction found, forward to webapp API

### Phase 3: Match Reply to Trade
**Goal**: Find the trade associated with the replied message

**Approach Options**:

**Option A: Message ID Lookup (Preferred)**
- Store `telegram_message_id` when creating trade
- Query trades by `telegram_message_id` to find matching trade
- Pros: Direct, fast, reliable
- Cons: Requires storing message IDs

**Option B: Signal Details Matching (Fallback)**
- If message ID not found, parse the original replied message
- Extract signal details (symbol, strike, option_type)
- Match against open trades with same details
- Pros: Works even if message ID not stored
- Cons: Less reliable (multiple trades with same symbol/strike possible)

**Implementation**:
1. **API Endpoint** (`webapp/api/paper_trading.py`):
   ```python
   @router.get("/find_by_message_id")
   async def find_trade_by_message_id(
       message_id: int,
       channel_id: int,
       current_user: User = Depends(get_current_user)
   ):
       """Find trade by Telegram message ID"""
   ```

2. **Signal Details Matching** (if message ID lookup fails):
   - Fetch the original message using `reply_to_msg_id`
   - Parse it as a signal
   - Match against open trades by symbol, strike, option_type, expiry

### Phase 4: Execute Trade Modifications
**Goal**: Apply instructions from reply messages

**Changes Required**:
1. **API Endpoint** (`webapp/api/paper_trading.py`):
   ```python
   @router.post("/modify_from_reply")
   async def modify_trade_from_reply(
       message_id: int,
       channel_id: int,
       instruction: str,  # "cancel" or "book_profits"
       current_user: User = Depends(get_current_user)
   ):
       """
       Modify trade based on Telegram reply message.
       
       Actions:
       - "cancel": Mark trade as cancelled (if not executed) or close if open
       - "book_profits": Exit trade immediately at current price or move SL to current price
       """
   ```

2. **Book Profits Logic**:
   - For open trades: Exit immediately at current LTP
   - Alternative: Move SL to current price (trailing SL to lock profits)
   - Decision: Exit immediately (simpler, clearer intent)

3. **Cancel Logic**:
   - If trade status is "open": Close trade with exit_reason="cancelled"
   - If trade has Zerodha orders: Cancel pending orders (future enhancement)

### Phase 5: Integration
**Goal**: Connect all components

**Flow**:
1. Orchestrator receives new message
2. Check if `message.reply_to` exists
3. If yes:
   - Extract `reply_to_msg_id`
   - Parse reply text for instructions
   - If instruction found:
     - Call webapp API `/api/trades/modify_from_reply` with message_id and instruction
4. Webapp API:
   - Find trade by message_id (or signal matching)
   - Execute instruction (exit or cancel)
   - Return success/error

## File Changes Summary

### New Files
- `otherRepos/telegram/reply_parser.py` - Parse reply message instructions

### Modified Files
1. `otherRepos/telegram/orchestrator.py`
   - Extract reply information from event
   - Call reply parser
   - Forward reply instructions to webapp

2. `webapp/api/paper_trading.py`
   - Add `telegram_message_id`, `telegram_channel_id`, `telegram_channel_name` to Trade model
   - Accept these fields in `SignalOrder` and `create_from_signal`
   - Add `/api/trades/find_by_message_id` endpoint
   - Add `/api/trades/modify_from_reply` endpoint

3. `otherRepos/telegram/message_handler.py`
   - Extract reply information in `extract_message_data`

## Testing Strategy

1. **Unit Tests**:
   - Test reply parser with various message formats
   - Test trade matching by message ID
   - Test trade matching by signal details

2. **Integration Tests**:
   - Create trade from signal (with message ID)
   - Send reply message
   - Verify trade is modified correctly

3. **Manual Testing**:
   - Monitor real Telegram channel
   - Verify reply messages are detected
   - Verify trades are modified as expected

## Edge Cases

1. **Multiple Trades from Same Signal**: Use most recent open trade
2. **Reply to Non-Signal Message**: Ignore (not a signal modification)
3. **Trade Already Closed**: Log warning, skip modification
4. **Message ID Not Found**: Fallback to signal details matching
5. **Ambiguous Instructions**: Prefer "book_profits" over "cancel" if both detected

## Future Enhancements

1. **Zerodha Integration**: Cancel pending orders when "cancel" instruction received
2. **SL Movement**: Instead of exiting, move SL to current price for "book profits"
3. **Partial Exit**: Support partial position closing
4. **Confidence Levels**: Track signal confidence and auto-exit low confidence signals


