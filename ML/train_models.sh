#!/usr/bin/env bash
set -euo pipefail

echo "===================================="
echo "Training ML Models"
echo "===================================="
echo
echo "This will train all 3 ML models..."
echo "Ensure you have reviewed 500+ patterns!"
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" run_complete_workflow.py train

echo
echo "===================================="
echo "Model Training Complete!"
echo "===================================="
echo
echo "Next: Run ./generate_signals.sh"
echo


