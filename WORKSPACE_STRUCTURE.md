# Super Swing - Clean Workspace Structure

## Overview
This workspace contains two main systems:
1. **ML Pattern Trading System** - Machine learning-based pattern detection and signal generation
2. **Web Application** - User interface for trading operations and monitoring

---

## Directory Structure

```
super-swing/
│
├── ML/                           # ML Pattern Trading System (Complete)
│   ├── pattern_detection/        # Pattern scanners (TA-Lib, YOLOv8)
│   ├── feature_engineering/      # Feature calculation for ML models
│   ├── models/                   # ML models (validity, success, risk-reward)
│   ├── training/                 # Model training pipeline
│   ├── backtesting/              # Realistic backtesting framework
│   ├── review_interface/         # Web UI for pattern review/labeling
│   ├── database/                 # SQLite schema for patterns/labels
│   ├── utils/                    # Data utilities, logger, market utils
│   ├── data/                     # Raw data, patterns, features, labels
│   ├── *.bat                     # Windows batch scripts for operations
│   ├── run_complete_workflow.py  # Main orchestration script
│   ├── signal_generator.py       # Daily signal generation
│   ├── test_single_stock.py      # Single stock testing
│   ├── test_batch_stocks.py      # Batch testing
│   ├── README.md                 # Comprehensive ML system documentation
│   ├── QUICKSTART.md             # Quick start guide
│   └── TROUBLESHOOTING.md        # Troubleshooting guide
│
├── webapp/                       # Web Application
│   ├── api/                      # API endpoints (analytics, backtest, etc.)
│   ├── templates/                # HTML templates (Jinja2)
│   ├── static/                   # CSS, JS, images
│   ├── data/                     # Application data (trades, watchlists)
│   ├── main.py                   # Flask application main file
│   ├── auth.py                   # Authentication module
│   ├── database.py               # Database operations
│   ├── zerodha_client.py         # Zerodha API integration
│   └── order_manager.py          # Order management
│
├── src/                          # Core Scanner Logic
│   ├── scanner/                  # Pattern detection, indicators, signals
│   ├── tests/                    # Unit and integration tests
│   ├── cli.py                    # Command-line interface
│   └── config.py                 # Scanner configuration
│
├── strategies/                   # Trading Strategies
│   ├── base_strategy.py          # Base strategy class
│   ├── swing_breakout_india.py   # Swing breakout strategy
│   ├── mean_reversion.py         # Mean reversion strategy
│   ├── momentum_btst.py          # Momentum BTST strategy
│   └── improved_btst.py          # Improved BTST strategy
│
├── utils/                        # Utility Modules
│   ├── ai_analyzer.py            # AI-powered stock analysis
│   ├── ai_fno_scanner.py         # F&O scanner with AI
│   ├── backtest_engine.py        # Backtesting engine
│   ├── email_service.py          # Email notifications
│   └── performance_tracker.py    # Performance tracking
│
├── models/                       # Data Models
│   └── api_credentials.py        # API credentials model
│
├── data/                         # Data Storage
│   ├── cache/                    # Cached stock data (1331 CSV files)
│   ├── raw/                      # Raw data (1531 CSV files)
│   ├── processed/                # Processed data
│   ├── output/                   # Analysis outputs, backtest results
│   └── performance/              # Performance metrics
│
├── examples/                     # Example Files
│   ├── symbols.csv               # Example symbol list
│   └── Ticker_List_NSE_India.csv # NSE ticker list
│
├── migrations/                   # Database Migrations
│   └── create_api_credentials_tables.sql
│
├── README.md                     # Main project documentation
├── env.example                   # Environment variables template
├── start_webapp.bat              # Start the web application
└── Ticker_List_NSE_India.csv     # Master NSE ticker list
```

---

## Key Components

### 1. ML System (`ML/`)
**Purpose**: Complete ML-driven pattern trading system for Indian stock markets

**Key Features**:
- Pattern detection (TA-Lib candlestick patterns)
- Feature engineering (60+ features per pattern)
- 3 ML models: Validity Classifier, Success Predictor, Risk-Reward Estimator
- Realistic backtesting framework
- Manual review interface for labeling
- Signal generation pipeline

**How to Use**:
```bash
cd ML
setup_system.bat          # First-time setup
scan_patterns.bat         # Scan for patterns
review_patterns.bat       # Review and label patterns
train_models.bat          # Train ML models
generate_signals.bat      # Generate trading signals
```

**Documentation**:
- `ML/README.md` - Complete system documentation
- `ML/QUICKSTART.md` - Quick start guide
- `ML/TROUBLESHOOTING.md` - Common issues and fixes

### 2. Web Application (`webapp/`)
**Purpose**: User-friendly interface for trading operations

**Key Features**:
- Interactive dashboard
- Real-time market data
- Zerodha integration
- Trade management
- Performance analytics
- AI-powered stock analysis
- F&O scanner

**How to Use**:
```bash
start_webapp.bat          # Start the web server
# Navigate to http://localhost:5000
```

### 3. Core Scanner (`src/`)
**Purpose**: Technical analysis and pattern detection engine

**Key Features**:
- Pattern detection (candlestick, chart patterns)
- Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Signal generation
- Custom pattern combinations

### 4. Trading Strategies (`strategies/`)
**Purpose**: Predefined trading strategies for various market conditions

**Available Strategies**:
- **Swing Breakout**: Trend-following breakout strategy
- **Mean Reversion**: Counter-trend mean reversion strategy
- **Momentum BTST**: Buy Today Sell Tomorrow momentum strategy
- **Improved BTST**: Enhanced BTST with better filters

### 5. Utilities (`utils/`)
**Purpose**: Reusable utility modules

**Key Utilities**:
- AI Analyzer: Google Gemini-powered stock analysis
- Backtest Engine: Strategy backtesting
- Email Service: Trade alerts and reports
- Performance Tracker: Track trading performance

---

## Getting Started

### Prerequisites
- Python 3.8+
- Required packages (see `ML/requirements.txt`)

### Setup Steps

1. **Install Dependencies**:
   ```bash
   cd ML
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   - Copy `env.example` to `.env`
   - Add your API credentials

3. **Choose Your Path**:

   **Path A: ML Pattern Trading System**
   ```bash
   cd ML
   # Read the README.md
   # Follow QUICKSTART.md
   ```

   **Path B: Web Application**
   ```bash
   # Configure Zerodha credentials
   start_webapp.bat
   ```

   **Path C: Custom Scanner**
   ```bash
   cd src
   python cli.py --help
   ```

---

## Data Management

### Data Storage (`data/`)
- **cache/**: Cached stock data from Yahoo Finance (1331 files)
- **raw/**: Raw historical data (1531 files)
- **processed/**: Cleaned and processed data
- **output/**: Analysis results, backtest reports, trade opportunities

### Data Cleaning
The data directories contain historical stock data. No cleanup needed unless storage is a concern.

---

## Quick Commands

### ML System
```bash
cd ML
scan_patterns.bat         # Scan for patterns (daily)
generate_signals.bat      # Generate trading signals
test_single_stock.py RELIANCE  # Test single stock
```

### Web Application
```bash
start_webapp.bat          # Start webapp
```

### Custom Analysis
```bash
python src/cli.py scan --symbols examples/symbols.csv
```

---

## Documentation

### Main Documentation
- `/README.md` - Project overview
- `/ML/README.md` - ML system complete guide
- `/ML/QUICKSTART.md` - Quick start guide
- This file - Workspace structure

### Technical References
- `/ML/PROJECT_SUMMARY.md` - Technical architecture
- `/ML/TROUBLESHOOTING.md` - Common issues
- `/ML/TESTING_RESULTS.md` - Test results

---

## Support

### Common Issues
- Feature engineering errors: See `ML/TROUBLESHOOTING.md`
- Pattern detection issues: Check `ML/logs/scanner.log`
- Webapp issues: Check `webapp/logs/`

### Testing
- Single stock: `python ML/test_single_stock.py SYMBOL`
- Batch stocks: `python ML/test_batch_stocks.py`

---

## Next Steps

1. **For ML Pattern Trading**:
   - Read `ML/README.md`
   - Run pattern scanner
   - Review and label patterns
   - Train models
   - Generate signals

2. **For Web Trading**:
   - Configure Zerodha API
   - Start webapp
   - Set up watchlists
   - Monitor trades

3. **For Custom Development**:
   - Explore `src/scanner/`
   - Add custom strategies to `strategies/`
   - Extend utilities in `utils/`

---

## Updates & Maintenance

### Regular Tasks
- **Daily**: Run pattern scanner, generate signals
- **Weekly**: Review performance, retrain models if needed
- **Monthly**: Clean up old cache files if storage is limited

### Log Management
- ML logs: `ML/logs/`
- Webapp logs: `webapp/logs/`

---

**Last Updated**: October 31, 2025
**Cleanup Date**: October 31, 2025
**Status**: Production-ready, clean workspace

