@echo off
echo ====================================
echo Pattern Review Interface
echo ====================================
echo.
echo Starting review interface...
echo Access at: http://localhost:5000
echo.
echo Keyboard shortcuts:
echo   V = Valid pattern
echo   X = Invalid pattern
echo   1-5 = Quality rating
echo   Space = Skip
echo.
echo Press Ctrl+C to stop the server
echo.

cd /d "%~dp0"

python run_complete_workflow.py review

