"""
Configuration settings for Telegram Channel Monitor
"""

# ============================================================================
# TELEGRAM API CREDENTIALS
# Get these from https://my.telegram.org/apps
# ============================================================================
API_ID = 33942643
API_HASH = '865403b9c9d0db46615571d189145a97'
PHONE_NUMBER = '+917385922115'

# ============================================================================
# CHANNEL SETTINGS
# ============================================================================
CHANNEL_NAME = 'BANKNIFTY NIFTY INTRADAY STOCK OPTIONS'
SESSION_NAME = 'channel_monitor'

# ============================================================================
# FILE PATHS
# ============================================================================
CSV_OUTPUT = 'telegram_messages.csv'
JSON_OUTPUT = 'telegram_messages.json'
EXCEL_OUTPUT = 'telegram_messages.xlsx'

# ============================================================================
# MONITORING SETTINGS
# ============================================================================
AUTO_SAVE_INTERVAL = 50  # Auto-save every N messages
MAX_MESSAGES_IN_MEMORY = 10000  # Max messages before forcing save

