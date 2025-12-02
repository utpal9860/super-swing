@echo off
echo ====================================
echo Training ML Models
echo ====================================
echo.

cd /d "%~dp0"

echo This will train all 3 ML models...
echo Ensure you have reviewed 500+ patterns!
echo.
pause

python run_complete_workflow.py train

echo.
echo ====================================
echo Model Training Complete!
echo ====================================
echo.
echo Next: Run generate_signals.bat
echo.
pause

