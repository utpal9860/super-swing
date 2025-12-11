#!/usr/bin/env bash
set -euo pipefail

echo "==============================================================================="
echo "MULTI-MODAL TRADING SIGNAL GENERATOR"
echo "==============================================================================="
echo
echo "100% FREE Implementation:"
echo "  - Pattern Detection: TA-Lib"
echo "  - Sentiment Analysis: Gemini + Google Search"
echo "  - Price Prediction: StatsForecast"
echo
echo "==============================================================================="
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

# Check .env
if [[ ! -f ".env" ]]; then
  echo "[WARNING] .env file not found!"
  echo
  echo "Creating .env file..."
  printf "GEMINI_API_KEY=your_gemini_api_key_here\n" > .env
  echo
  echo "Please edit .env and add your Gemini API key."
  echo "Get it from: https://makersuite.google.com/app/apikey"
  echo
  exit 1
fi

UNIVERSE="test"
DETAILS=""
OUTPUT="multimodal_signals.csv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --test)
      UNIVERSE="test"
      shift
      ;;
    --fno)
      UNIVERSE="fno_top20"
      shift
      ;;
    --details)
      DETAILS="--details"
      shift
      ;;
    --output)
      OUTPUT="${2:-$OUTPUT}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

echo "Starting workflow with universe: $UNIVERSE"
echo

set +e
"$PYTHON_BIN" run_multimodal_workflow.py --universe "$UNIVERSE" --output "$OUTPUT" $DETAILS
EXIT_CODE=$?
set -e

if [[ $EXIT_CODE -ne 0 ]]; then
  echo
  echo "[ERROR] Workflow failed! Check the logs for details."
  exit $EXIT_CODE
fi

echo
echo "==============================================================================="
echo "Workflow complete! Check $OUTPUT for signals."
echo "==============================================================================="
echo


