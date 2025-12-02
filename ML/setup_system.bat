@echo off
echo ====================================
echo ML Pattern Trading System - Setup
echo ====================================
echo.

cd /d "%~dp0"

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Creating database and directories...
python run_complete_workflow.py setup

echo.
echo ====================================
echo Setup Complete!
echo ====================================
echo.
echo Next steps:
echo 1. Run: scan_patterns.bat
echo 2. Run: review_patterns.bat
echo 3. Review 500-1000 patterns
echo 4. Run: train_models.bat
echo.
pause

