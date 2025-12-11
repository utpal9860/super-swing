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
CHANNEL_NAME = '-1001615795252'
# Optional: monitor multiple channels at once (IDs like '-100...', or usernames like '@handle' or plain)
# Include both your primary and test channel here. Example adds the new '007' channel identifier.
CHANNELS = ['-1001615795252', '-1003295460088']
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

# ============================================================================
# WEBAPP INTEGRATION
# ============================================================================
# Set token from your webapp localStorage auth_token after login.
WEBAPP_API_URL = 'http://localhost:8000'
WEBAPP_AUTH_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyX2lZZXc1dDlRcW4wVXcxeVhDemZkLUEiLCJleHAiOjE3NjQ4MzkzNTl9.L2psvo37paD_uwCjbnwW8ii-p5VT6FZGpfKGfJ0NMTo'  # e.g., 'eyJhbGciOiJI...'
WEBAPP_POST_ENABLED = True  # set True to forward parsed signals to webapp
DEBUG_PRINT_NON_MATCHING = True  # set True to print skipped (non-matching) texts for debugging
WEBAPP_API_KEY = 'U7DSZB_BAyYuYzlOO0Okcqh5w4x95XpQI4woDbbSt5g'  # Optional static API key (use instead of token)
WEBAPP_FOR_USER_USERNAME = 'utpal9860'  # Optional: route trades to this username when using API key

