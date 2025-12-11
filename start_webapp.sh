#!/usr/bin/env bash
set -euo pipefail

echo
echo "========================================"
echo "  SuperTrend Trading Platform"
echo "  Starting Web Application..."
echo "========================================"
echo
echo "Dashboard will open at: http://localhost:8000"
echo "API Documentation at: http://localhost:8000/docs"
echo
echo "Press Ctrl+C to stop the server"
echo

#!/bin/bash
cd /home/ue/utpal/super-swing
source venv/bin/activate
# Load .env into environment if present (for JWT_SECRET_KEY, etc.)
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
# Bypass auth locally
export BYPASS_AUTH=true
uvicorn webapp.main:app --reload --port 8000

