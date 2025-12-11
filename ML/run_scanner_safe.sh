#!/usr/bin/env bash
set -euo pipefail

echo "===================================="
echo "Safe Pattern Scanner"
echo "===================================="
echo
echo "This will scan stocks with error handling"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" run_complete_workflow.py scan --universe FNO --recent 7

echo
echo "===================================="
echo "Scan Complete!"
echo "===================================="
echo
echo "Check ML/data/patterns.db for results"
echo


