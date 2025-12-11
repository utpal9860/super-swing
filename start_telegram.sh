#!/usr/bin/env bash
set -euo pipefail

echo
echo "========================================"
echo "  SuperTrend Telegram Monitor"
echo "  Starting Orchestrator..."
echo "========================================"
echo

PROJECT_ROOT="/home/ue/utpal/super-swing"
cd "$PROJECT_ROOT"

# Activate virtualenv
if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
else
  echo "[ERROR] venv not found at $PROJECT_ROOT/venv"
  echo "Create it with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && pip install -r otherRepos/telegram/requirements.txt"
  exit 1
fi

# Load .env if present (optional; used by webapp auth keys)
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

python "otherRepos/telegram/orchestrator.py"


