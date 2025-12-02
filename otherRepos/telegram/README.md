# Telegram Channel Monitor

Modular system to monitor Telegram channels and save messages to CSV in real-time.

## Project Structure

```
telegram/
├── config.py              # Configuration settings
├── telegram_client.py     # Telegram authentication & connection
├── message_handler.py     # Message processing & extraction
├── data_storage.py        # CSV/JSON/Excel export
├── analytics.py           # Analytics & statistics
├── display.py             # Display formatting
├── orchestrator.py        # Main orchestrator (ENTRY POINT)
└── README.md             # This file
```

## Setup

1. **Install dependencies**:
```bash
pip install telethon pandas openpyxl
```

2. **Configure credentials**:
Edit `config.py` and add your:
- `API_ID` and `API_HASH` from https://my.telegram.org/apps
- `PHONE_NUMBER`
- `CHANNEL_NAME`

3. **Run**:
```bash
python orchestrator.py
```

## Module Responsibilities

### 1. config.py
- Stores all configuration
- API credentials
- File paths
- Settings

### 2. telegram_client.py
**TelegramChannelClient** class handles:
- Authentication with Telegram
- Getting channel entity
- Listing all channels
- Fetching recent messages
- Connection management

### 3. message_handler.py
**MessageHandler** class handles:
- Extracting message data
- Extracting links from text
- Detecting media types
- Searching messages
- Filtering by date/media type

### 4. data_storage.py
**DataStorage** class handles:
- Storing messages in memory
- Saving to CSV
- Saving to JSON
- Saving to Excel
- Auto-save functionality
- Data management

### 5. analytics.py
**Analytics** class provides:
- Basic statistics
- Media statistics
- Link statistics
- Top messages
- Time distribution
- Comprehensive summaries

### 6. display.py
**Display** class provides:
- HTML formatting (for Jupyter)
- Console formatting
- Status display
- Pretty printing

### 7. orchestrator.py
**TelegramMonitorOrchestrator** class:
- Coordinates all modules
- Main workflow management
- Entry point for the system

## Usage Examples

### Basic Usage (Run Automatically)
```bash
python orchestrator.py
```

### Advanced Usage (Custom Control)
```python
from orchestrator import TelegramMonitorOrchestrator
import asyncio

async def custom_workflow():
    # Create orchestrator
    orch = TelegramMonitorOrchestrator()
    
    # Initialize
    await orch.initialize()
    
    # List available channels
    await orch.list_channels()
    
    # Fetch recent messages (without monitoring)
    await orch.fetch_recent_messages(limit=50)
    
    # Search messages
    results = orch.search_messages("breaking news")
    
    # Show analytics
    orch.show_analytics()
    
    # Export data
    orch.export_data()
    
    # Start real-time monitoring (runs until Ctrl+C)
    await orch.start_monitoring()

# Run
asyncio.run(custom_workflow())
```

### Search Messages
```python
# After collecting messages
results = orch.search_messages("stock", case_sensitive=False)
print(f"Found {len(results)} messages")
```

### Export Data
```python
# Export to all formats (CSV, JSON, Excel)
orch.export_data()

# Or export individually
orch.data_storage.save_to_csv('my_messages.csv')
orch.data_storage.save_to_json('my_messages.json')
```

### Get Analytics
```python
# Show comprehensive analytics
orch.show_analytics()

# Or get specific stats
stats = orch.analytics.get_basic_stats()
media_stats = orch.analytics.get_media_stats()
top_msgs = orch.analytics.get_top_messages(n=10)
```

## Features

✅ Real-time message monitoring
✅ **Rate limit protection** (no more blocks!)
✅ **Flood error handling** (auto-wait and retry)
✅ **Health monitoring** (connection status checks)
✅ Auto-save every N messages
✅ Export to CSV, JSON, Excel
✅ Link extraction
✅ Media type detection
✅ Message search
✅ Analytics & statistics
✅ Modular & maintainable
✅ Easy to extend
✅ **24/7 stable operation**

## Output Files

- `telegram_messages.csv` - All messages in CSV format
- `telegram_messages.json` - All messages in JSON format
- `telegram_messages.xlsx` - All messages in Excel format

## Extending the System

### Add Custom Processing
Edit `message_handler.py` and add your function:
```python
@staticmethod
def extract_stock_symbols(text):
    """Extract stock symbols from text"""
    pattern = r'\b[A-Z]{3,5}\b'
    return re.findall(pattern, text)
```

### Add Custom Analytics
Edit `analytics.py` and add:
```python
def get_sentiment_analysis(self):
    """Analyze message sentiment"""
    # Your code here
    pass
```

### Add Custom Export Format
Edit `data_storage.py` and add:
```python
def save_to_database(self):
    """Save to database"""
    # Your code here
    pass
```

## Troubleshooting

**Can't access channel?**
- Ensure you're a member
- Try using @username format
- Check spelling

**Authentication fails?**
- Verify API_ID and API_HASH
- Check phone number format (+country code)

**Import errors?**
- Install: `pip install telethon pandas openpyxl`

## License

MIT

