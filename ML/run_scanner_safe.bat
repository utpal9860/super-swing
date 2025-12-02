@echo off
echo ====================================
echo Safe Pattern Scanner
echo ====================================
echo.
echo This will scan stocks with error handling
echo.
pause

cd /d "%~dp0"

python run_complete_workflow.py scan --universe FNO --recent 7

echo.
echo ====================================
echo Scan Complete!
echo ====================================
echo.
echo Check ML/data/patterns.db for results
echo.
pause

