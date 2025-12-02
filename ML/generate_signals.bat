@echo off
echo ====================================
echo Generating Trading Signals
echo ====================================
echo.

cd /d "%~dp0"

python run_complete_workflow.py signals --universe FNO

echo.
echo Signals saved to data/signals_*.csv
echo.
pause

