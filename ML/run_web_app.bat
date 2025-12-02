@echo off
REM Multi-Modal Trading System - Web Application Launcher
REM Beautiful UI for pattern detection, sentiment analysis, and price prediction

echo ================================================================================
echo MULTI-MODAL TRADING SYSTEM - WEB UI
echo ================================================================================
echo.
echo Starting web server...
echo.
echo Features:
echo   - Pattern Detection (TA-Lib)
echo   - Sentiment Analysis (Gemini + Google Search)
echo   - Price Prediction (StatsForecast)
echo   - Interactive Charts (Plotly)
echo.
echo ================================================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

REM Check .env file
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Please create .env file with: GEMINI_API_KEY=your_key_here
    echo.
    pause
)

REM Run the web app
cd web_app
python app.py

if errorlevel 1 (
    echo.
    echo [ERROR] Web app failed to start!
    echo.
    echo Common issues:
    echo   1. Missing dependencies: pip install flask flask-cors plotly
    echo   2. GEMINI_API_KEY not set in .env
    echo   3. Port 5001 already in use
    echo.
    pause
    exit /b 1
)

