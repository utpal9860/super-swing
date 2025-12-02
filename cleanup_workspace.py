"""
Cleanup Script - Remove temporary and redundant files
Keeps only core ML logic and webapp
"""
import os
import shutil
from pathlib import Path

print("="*80)
print("WORKSPACE CLEANUP")
print("="*80)

# Files and folders to remove
REMOVE_FILES = [
    # LSTM test files (temporary)
    "fetch_lt_data_for_lstm.py",
    "backtest_lstm_lt.py",
    "analyze_backtest_results.py",
    "LT_backtest_sequences_20251031.csv",
    "LT_backtest_results_template_20251031.csv",
    "LT_data_20251031.csv",
    
    # Old backtest scripts (not part of core ML)
    "backtest_2025_with_proper_risk.py",
    "backtest_adaptive_2025.csv",
    "backtest_btst_winners.py",
    "backtest_year_2025.py",
    "btst_backtest.py",
    "btst_opportunities_2025-10-24.csv",
    "btst_opportunities_2025-10-25.csv",
    "btst_opportunities_2025-10-26.csv",
    "btst_scanner.py",
    "btst_winners_backtest_2022-01-01_to_2024-12-31.csv",
    "reversion_opportunities_2025-10-24.csv",
    "swing_opportunities_2025-10-24.csv",
    
    # Standalone scanner scripts (functionality in ML or webapp)
    "scanner_mean_reversion.py",
    "scanner_momentum_btst.py",
    "scanner_swing_supertrend.py",
    "run_pullback_scanner.py",
    "weekly_trade_scanner.py",
    
    # Test and experimental scripts
    "create_quality_watchlist.py",
    "test_email_config.py",
    "test_pullback_strategy.py",
    "strategy_discovery.py",
    
    # EOD and monitoring scripts (if not needed)
    "eod_monitor.py",
    "eod_config.json",
    "trade_health_monitor.py",
    "trailing_sl_hourly.py",
    "setup_trailing_cron.py",
    "market_data_fetcher.py",
    
    # Temporary batch files (keep only start_webapp.bat)
    "run_eod_check.bat",
    "run_multi_year_backtest.bat",
    "RUN_WEEKLY_SCANNER.bat",
    "RUN_YEAR_2025_BACKTEST.bat",
    "schedule_eod_check.bat",
    
    # Setup scripts (already used)
    "setup_env.ps1",
    
    # This cleanup script itself
    "cleanup_workspace.py",
]

# Documentation files to remove (excessive progress tracking)
REMOVE_DOCS = [
    "AI_BEARER_TOKEN_IMPLEMENTATION_START.md",
    "AI_FNO_SCANNER_COMPLETE.md",
    "AI_IMPLEMENTATION_PROGRESS.md",
    "AI_IMPLEMENTATION_SUMMARY.md",
    "AI_INTEGRATION_COMPLETE.md",
    "AI_INTEGRATION_STATUS.md",
    "AI_SCANNER_IMPLEMENTATION.md",
    "AI_VISUAL_FLOW.md",
    "ANALYTICS_FIX_SUMMARY.md",
    "API_CREDENTIALS_SUMMARY.md",
    "AUTHENTICATION_FIXED.md",
    "BEARER_TOKEN_IMPLEMENTATION_COMPLETE.md",
    "BEARER_TOKEN_PROGRESS.md",
    "BEARER_TOKEN_UPDATE.md",
    "EMAIL_BACKEND_READY.md",
    "EMAIL_IMPLEMENTATION_SUMMARY.md",
    "EMAIL_QUICK_CARD.txt",
    "EMAIL_SETUP_GUIDE.md",
    "EOD_HEALTH_INTEGRATION_COMPLETE.txt",
    "FNO_LIVE_DATA_COMPLETE.md",
    "FNO_TABLE_INTEGRATION_COMPLETE.md",
    "GEMINI_IMPLEMENTATION_COMPLETE.md",
    "GEMINI_SETUP_GUIDE.md",
    "GET_BEARER_TOKEN_GUIDE.md",
    "IMPLEMENTATION_COMPLETE.md",
    "IMPLEMENTATION_LOG.md",
    "IMPROVED_BTST_IMPLEMENTATION.md",
    "ML_IMPLEMENTATION_COMPLETE.md",
    "PROFILE_PAGE_FIXED.md",
    "PROGRESS_REPORT.md",
    "PROJECT_COMPLETION_SUMMARY.md",
    "SETUP_EMAIL_NOW.txt",
    "START_HERE.txt",
    "TARGET_ZERO_FIX.md",
    "THEME_IMPLEMENTATION.md",
    "TRADE_HEALTH_GUIDE.md",
    "TRADE_HEALTH_SUMMARY.txt",
    "TRAILING_SL_IMPLEMENTATION.md",
    "TRAILING_SL_UI_GUIDE.md",
    "WATCHLIST_AI_COMPLETE.md",
]

# Folders to remove entirely
REMOVE_FOLDERS = [
    "archive",  # Already archived
    "backup_20251022_034914",  # Old backup
    "docs_consolidated",  # Consolidated docs (redundant)
    "experimental_strategies",  # Experimental, not core
    "strategy_research_results",  # Research outputs
    "logs",  # Old logs
    "__pycache__",  # Python cache
]

# Keep these folders (CORE)
KEEP_FOLDERS = [
    "ML",  # Core ML logic
    "webapp",  # Web application
    "src",  # Core scanner logic
    "strategies",  # Core strategies
    "utils",  # Utilities
    "models",  # Data models
    "data",  # Data storage
    "examples",  # Example files
    "migrations",  # Database migrations
]

# Keep these files (ESSENTIAL)
KEEP_FILES = [
    "README.md",
    "env.example",
    "start_webapp.bat",
    "Ticker_List_NSE_India.csv",
]

def remove_file(filepath):
    """Remove a file if it exists"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[REMOVED] {filepath}")
            return True
        else:
            print(f"[SKIP] Not found: {filepath}")
            return False
    except Exception as e:
        print(f"[ERROR] Could not remove {filepath}: {e}")
        return False

def remove_folder(folderpath):
    """Remove a folder if it exists"""
    try:
        if os.path.exists(folderpath):
            shutil.rmtree(folderpath)
            print(f"[REMOVED] {folderpath}/")
            return True
        else:
            print(f"[SKIP] Not found: {folderpath}/")
            return False
    except Exception as e:
        print(f"[ERROR] Could not remove {folderpath}: {e}")
        return False

# Execute cleanup
print("\n" + "="*80)
print("STEP 1: Removing temporary files")
print("="*80)

files_removed = 0
for file in REMOVE_FILES:
    if remove_file(file):
        files_removed += 1

print(f"\n[OK] Removed {files_removed} temporary files")

print("\n" + "="*80)
print("STEP 2: Removing documentation files")
print("="*80)

docs_removed = 0
for doc in REMOVE_DOCS:
    if remove_file(doc):
        docs_removed += 1

print(f"\n[OK] Removed {docs_removed} documentation files")

print("\n" + "="*80)
print("STEP 3: Removing temporary folders")
print("="*80)

folders_removed = 0
for folder in REMOVE_FOLDERS:
    if remove_folder(folder):
        folders_removed += 1

print(f"\n[OK] Removed {folders_removed} folders")

print("\n" + "="*80)
print("CLEANUP SUMMARY")
print("="*80)

print(f"""
Total Removed:
  - Files: {files_removed + docs_removed}
  - Folders: {folders_removed}

Core Folders Preserved:
""")

for folder in KEEP_FOLDERS:
    if os.path.exists(folder):
        print(f"  [OK] {folder}/")

print(f"""
Essential Files Preserved:
""")

for file in KEEP_FILES:
    if os.path.exists(file):
        print(f"  [OK] {file}")

print("\n" + "="*80)
print("WORKSPACE STRUCTURE (After Cleanup)")
print("="*80)

print("""
super-swing/
├── ML/                    # Core ML pattern trading system
├── webapp/                # Web application
├── src/                   # Core scanner logic
├── strategies/            # Trading strategies
├── utils/                 # Utility functions
├── models/                # Data models
├── data/                  # Data storage (cache, raw, processed)
├── examples/              # Example files
├── migrations/            # Database migrations
├── README.md              # Main documentation
├── env.example            # Environment variables template
├── start_webapp.bat       # Start the web app
└── Ticker_List_NSE_India.csv  # NSE ticker list
""")

print("\n" + "="*80)
print("CLEANUP COMPLETE!")
print("="*80)
print("\nYour workspace is now clean and organized.")
print("Only core ML logic and webapp remain.\n")

