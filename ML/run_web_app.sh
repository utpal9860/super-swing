#!/usr/bin/env bash
set -euo pipefail

echo "==============================================================================="
echo "MULTI-MODAL TRADING SYSTEM - WEB UI"
echo "==============================================================================="
echo
echo "Starting web server..."
echo
echo "Features:"
echo "  - Pattern Detection (TA-Lib)"
echo "  - Sentiment Analysis (Gemini + Google Search)"
echo "  - Price Prediction (StatsForecast)"
echo "  - Interactive Charts (Plotly)"
echo
echo "==============================================================================="
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

if [[ ! -f ".env" ]]; then
  echo "[WARNING] .env file not found!"
  echo "Please create .env file with: GEMINI_API_KEY=your_key_here"
  echo
fi

cd "$SCRIPT_DIR/web_app"
"$PYTHON_BIN" app.py


