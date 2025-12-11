#!/usr/bin/env bash
set -euo pipefail

echo "===================================="
echo "ML Pattern Trading System - Setup"
echo "===================================="
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

echo "Installing Python dependencies..."
"$PYTHON_BIN" -m pip install -r requirements.txt

echo
echo "Creating database and directories..."
"$PYTHON_BIN" run_complete_workflow.py setup

echo
echo "===================================="
echo "Setup Complete!"
echo "===================================="
echo
echo "Next steps:"
echo "1. Run: ./scan_patterns.sh"
echo "2. Run: ./review_patterns.sh"
echo "3. Review 500-1000 patterns"
echo "4. Run: ./train_models.sh"
echo


