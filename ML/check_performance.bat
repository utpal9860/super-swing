@echo off
echo ====================================
echo Performance Tracking
echo ====================================
echo.

cd /d "%~dp0"

python run_complete_workflow.py performance

echo.
echo Performance report saved to data/performance_report_*.txt
echo.
pause

