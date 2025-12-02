@echo off
echo ====================================
echo Scanning for Patterns
echo ====================================
echo.

cd /d "%~dp0"

python run_complete_workflow.py scan --universe FNO

echo.
echo ====================================
echo Pattern Scan Complete!
echo ====================================
echo.
echo Next: Run review_patterns.bat to label patterns
echo.
pause

