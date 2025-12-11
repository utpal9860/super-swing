#!/usr/bin/env bash
set -euo pipefail

echo "===================================="
echo "Pattern Review Interface"
echo "===================================="
echo
echo "Starting review interface..."
echo "Access at: http://localhost:5000"
echo
echo "Keyboard shortcuts:"
echo "  V = Valid pattern"
echo "  X = Invalid pattern"
echo "  1-5 = Quality rating"
echo "  Space = Skip"
echo
echo "Press Ctrl+C to stop the server"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" run_complete_workflow.py review


