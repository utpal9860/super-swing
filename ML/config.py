"""
Configuration file for ML Pattern Trading System
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"

# Data subdirectories
RAW_DATA_DIR = DATA_DIR / "raw"
PATTERNS_DIR = DATA_DIR / "patterns"
FEATURES_DIR = DATA_DIR / "features"
LABELED_DIR = DATA_DIR / "labeled"

# Database
DB_PATH = DATA_DIR / "patterns.db"

# Create directories if they don't exist
for directory in [DATA_DIR, MODELS_DIR, LOGS_DIR, RAW_DATA_DIR, 
                  PATTERNS_DIR, FEATURES_DIR, LABELED_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Market Configuration
MARKET_CONFIG = {
    "exchange": ["NSE", "BSE"],
    "universe": "F&O",  # F&O stocks, Nifty50, Nifty100, Nifty200
    "timeframes": ["1d", "4h", "1h"],  # Daily primary, 4H/1H secondary
    "trading_style": "swing",
    "holding_period": (3, 20),  # 3-20 days
}

# Data Sources
DATA_SOURCES = {
    "price_data": "yahoo",  # yahoo, nsepy, or custom API
    "nse_api": "https://www.nseindia.com",
    "fno_stocks_url": "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O",
}

# Pattern Detection Configuration
PATTERN_CONFIG = {
    "methods": ["talib", "custom"],  # TA-Lib + custom patterns
    "min_pattern_samples": 500,  # Minimum patterns to train models
    "target_pattern_samples": 1000,
    "confidence_threshold": 0.5,  # ML detection confidence
    "lookback_period": 730,  # 2 years of historical data
}

# TA-Lib Pattern List (60+ candlestick patterns)
TALIB_PATTERNS = [
    'CDL2CROWS', 'CDL3BLACKCROWS', 'CDL3INSIDE', 'CDL3LINESTRIKE',
    'CDL3OUTSIDE', 'CDL3STARSINSOUTH', 'CDL3WHITESOLDIERS', 'CDLABANDONEDBABY',
    'CDLADVANCEBLOCK', 'CDLBELTHOLD', 'CDLBREAKAWAY', 'CDLCLOSINGMARUBOZU',
    'CDLCONCEALBABYSWALL', 'CDLCOUNTERATTACK', 'CDLDARKCLOUDCOVER', 'CDLDOJI',
    'CDLDOJISTAR', 'CDLDRAGONFLYDOJI', 'CDLENGULFING', 'CDLEVENINGDOJISTAR',
    'CDLEVENINGSTAR', 'CDLGAPSIDESIDEWHITE', 'CDLGRAVESTONEDOJI', 'CDLHAMMER',
    'CDLHANGINGMAN', 'CDLHARAMI', 'CDLHARAMICROSS', 'CDLHIGHWAVE',
    'CDLHIKKAKE', 'CDLHIKKAKEMOD', 'CDLHOMINGPIGEON', 'CDLIDENTICAL3CROWS',
    'CDLINNECK', 'CDLINVERTEDHAMMER', 'CDLKICKING', 'CDLKICKINGBYLENGTH',
    'CDLLADDERBOTTOM', 'CDLLONGLEGGEDDOJI', 'CDLLONGLINE', 'CDLMARUBOZU',
    'CDLMATCHINGLOW', 'CDLMATHOLD', 'CDLMORNINGDOJISTAR', 'CDLMORNINGSTAR',
    'CDLONNECK', 'CDLPIERCING', 'CDLRICKSHAWMAN', 'CDLRISEFALL3METHODS',
    'CDLSEPARATINGLINES', 'CDLSHOOTINGSTAR', 'CDLSHORTLINE', 'CDLSPINNINGTOP',
    'CDLSTALLEDPATTERN', 'CDLSTICKSANDWICH', 'CDLTAKURI', 'CDLTASUKIGAP',
    'CDLTHRUSTING', 'CDLTRISTAR', 'CDLUNIQUE3RIVER', 'CDLUPSIDEGAP2CROWS',
    'CDLXSIDEGAP3METHODS'
]

# Custom Chart Patterns (to be implemented)
CUSTOM_PATTERNS = [
    'DOUBLE_BOTTOM', 'DOUBLE_TOP',
    'HEAD_AND_SHOULDERS', 'INVERSE_HEAD_AND_SHOULDERS',
    'ASCENDING_TRIANGLE', 'DESCENDING_TRIANGLE', 'SYMMETRICAL_TRIANGLE',
    'RISING_WEDGE', 'FALLING_WEDGE',
    'CUP_AND_HANDLE', 'INVERSE_CUP_AND_HANDLE',
    'FLAG', 'PENNANT',
    'CHANNEL_UP', 'CHANNEL_DOWN',
]

# Labeling Configuration
LABELING_CONFIG = {
    "outcome_period": 10,  # Days to wait for pattern outcome
    "success_criteria": "target_hit",  # target_hit, stop_loss, time_based
    "target_method": "pattern_height",  # Pattern height projection
    "stop_loss_method": "pattern_low",  # Below pattern low
    "neutral_threshold": 0.5,  # % gain/loss to be considered neutral
}

# Feature Engineering
FEATURE_CONFIG = {
    "technical_indicators": {
        "rsi_period": 14,
        "atr_period": 14,
        "volume_ma_period": 20,
        "sma_periods": [20, 50, 200],
        "ema_periods": [12, 26],
        "bb_period": 20,
        "bb_std": 2,
    },
    "market_indicators": {
        "nifty_index": "^NSEI",
        "bank_nifty": "^NSEBANK",
        "india_vix": "INDIA VIX",
    },
    "temporal_features": True,
    "fundamental_features": False,  # Enable later if needed
}

# Model Configuration
MODEL_CONFIG = {
    "model_1_validity": {
        "type": "RandomForestClassifier",
        "params": {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 20,
            "min_samples_leaf": 10,
            "class_weight": "balanced",
            "random_state": 42,
        },
        "threshold": 0.70,  # Probability threshold for validity
    },
    "model_2_success": {
        "type": "XGBClassifier",
        "params": {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        },
        "threshold": 0.60,  # Probability threshold for success
    },
    "model_3_risk_reward": {
        "type": "RandomForestRegressor",
        "params": {
            "n_estimators": 100,
            "max_depth": 8,
            "min_samples_split": 10,
            "random_state": 42,
        },
    },
    "cv_splits": 5,  # Time series cross-validation splits
    "test_size": 0.15,
    "validation_size": 0.15,
}

# Backtesting Configuration
BACKTEST_CONFIG = {
    "initial_capital": 100000,  # ₹1 lakh
    "position_size": 0.05,  # 5% per trade
    "max_positions": 5,
    "slippage_pct": 0.001,  # 0.1%
    "brokerage_per_trade": 20,  # ₹20
    
    # Indian market constraints
    "circuit_breaker_limit": 0.20,  # 20% daily limit
    "min_volume_threshold": 100000,  # Minimum daily volume
    "check_fo_ban": True,
    "check_holidays": True,
    
    # Transaction costs (Indian market)
    "costs": {
        "brokerage_pct": 0.0005,  # 0.05% or ₹20 whichever lower
        "stt_pct": 0.001,  # 0.1% on sell side
        "exchange_charges_pct": 0.0000325,  # NSE charges
        "gst_pct": 0.18,  # 18% on brokerage + exchange
        "sebi_charges_pct": 0.0000001,
        "stamp_duty_pct": 0.00015,  # 0.015% on buy side
    },
    
    # Exit rules
    "max_holding_days": 20,
    "use_trailing_stop": True,
    "trailing_stop_pct": 0.05,  # 5% trailing stop
}

# Trading Signals Configuration
SIGNAL_CONFIG = {
    "min_success_probability": 0.60,  # 60% minimum
    "min_expected_gain": 3.0,  # 3% minimum expected gain
    "max_signals_per_day": 10,
    "rank_by": "expected_gain",  # success_prob, expected_gain, risk_reward
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": LOGS_DIR / "ml_system.log",
}

# NSE Trading Holidays 2024-2025 (update annually)
NSE_HOLIDAYS = [
    "2024-01-26",  # Republic Day
    "2024-03-08",  # Mahashivratri
    "2024-03-25",  # Holi
    "2024-03-29",  # Good Friday
    "2024-04-11",  # Id-Ul-Fitr
    "2024-04-17",  # Ram Navami
    "2024-04-21",  # Mahavir Jayanti
    "2024-05-01",  # Maharashtra Day
    "2024-05-23",  # Buddha Purnima
    "2024-06-17",  # Bakri Id
    "2024-07-17",  # Muharram
    "2024-08-15",  # Independence Day
    "2024-08-26",  # Janmashtami
    "2024-10-02",  # Gandhi Jayanti
    "2024-10-12",  # Dussehra
    "2024-11-01",  # Diwali Laxmi Pujan
    "2024-11-02",  # Diwali Balipratipada
    "2024-11-15",  # Gurunanak Jayanti
    "2024-12-25",  # Christmas
    "2025-01-26",  # Republic Day
    "2025-03-14",  # Holi
    "2025-03-31",  # Id-Ul-Fitr
    "2025-04-10",  # Mahavir Jayanti
    "2025-04-14",  # Dr.Ambedkar Jayanti
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-08-15",  # Independence Day
    "2025-08-27",  # Janmashtami
    "2025-10-02",  # Gandhi Jayanti
    "2025-10-21",  # Dussehra
    "2025-11-01",  # Diwali Laxmi Pujan
    "2025-11-05",  # Gurunanak Jayanti
    "2025-12-25",  # Christmas
]

# Stock Universe (will be fetched dynamically)
STOCK_UNIVERSE = {
    "nifty_50": [],  # To be populated
    "nifty_100": [],
    "nifty_200": [],
    "fno_stocks": [],
}

# Print configuration on import
if __name__ == "__main__":
    print(f"ML Pattern Trading System Configuration")
    print(f"========================================")
    print(f"Base Directory: {BASE_DIR}")
    print(f"Data Directory: {DATA_DIR}")
    print(f"Models Directory: {MODELS_DIR}")
    print(f"Database: {DB_PATH}")
    print(f"TA-Lib Patterns: {len(TALIB_PATTERNS)}")
    print(f"Custom Patterns: {len(CUSTOM_PATTERNS)}")

