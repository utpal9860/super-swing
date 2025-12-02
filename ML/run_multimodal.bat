@echo off
REM Multi-Modal Trading Signal Generator - Windows Launcher
REM Uses Pattern Detection + Sentiment Analysis + Price Prediction

echo ================================================================================
echo MULTI-MODAL TRADING SIGNAL GENERATOR
echo ================================================================================
echo.
echo 100%% FREE Implementation:
echo   - Pattern Detection: TA-Lib
echo   - Sentiment Analysis: Gemini + Google Search
echo   - Price Prediction: StatsForecast
echo.
echo ================================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo.
    echo Creating .env file...
    echo GEMINI_API_KEY=your_gemini_api_key_here > .env
    echo.
    echo Please edit .env and add your Gemini API key.
    echo Get it from: https://makersuite.google.com/app/apikey
    echo.
    pause
    exit /b 1
)

REM Parse command line arguments
set UNIVERSE=test
set DETAILS=
set OUTPUT=multimodal_signals.csv

:parse_args
if "%1"=="" goto run_workflow
if /i "%1"=="--test" (
    set UNIVERSE=test
    shift
    goto parse_args
)
if /i "%1"=="--fno" (
    set UNIVERSE=fno_top20
    shift
    goto parse_args
)
if /i "%1"=="--details" (
    set DETAILS=--details
    shift
    goto parse_args
)
shift
goto parse_args

:run_workflow
echo Starting workflow with universe: %UNIVERSE%
echo.

REM Run the workflow
python run_multimodal_workflow.py --universe %UNIVERSE% --output %OUTPUT% %DETAILS%

if errorlevel 1 (
    echo.
    echo [ERROR] Workflow failed! Check the logs for details.
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo Workflow complete! Check %OUTPUT% for signals.
echo ================================================================================
echo.
pause

