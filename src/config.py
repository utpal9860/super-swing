"""Configuration constants and default parameters."""
import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUT_DIR = DATA_DIR / "output"

# Create directories if they don't exist
for dir_path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# SuperTrend default parameters
DEFAULT_ATR_PERIOD = 10
DEFAULT_MULTIPLIER = 3.0
DEFAULT_TIMEFRAME = "1wk"

# Analysis defaults
DEFAULT_ABS_THRESHOLD = 10.0  # percentage
DEFAULT_MIN_TRADES = 1

# Date formats
DATE_FORMAT = "%Y-%m-%d"

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

