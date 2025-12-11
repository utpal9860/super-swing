#!/usr/bin/env bash
set -euo pipefail

echo "===================================="
echo "Generating Trading Signals"
echo "===================================="
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" run_complete_workflow.py signals --universe FNO

echo
echo "Signals saved to data/signals_*.csv"
echo


