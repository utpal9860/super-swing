#!/usr/bin/env bash
set -euo pipefail

echo "===================================="
echo "Scanning for Patterns"
echo "===================================="
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" run_complete_workflow.py scan --universe FNO

echo
echo "====================================="
echo "Pattern Scan Complete!"
echo "====================================="
echo
echo "Next: Run ./review_patterns.sh to label patterns"
echo


