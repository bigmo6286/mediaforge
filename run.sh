#!/usr/bin/env bash
# Start MediaForge as a SINGLE server (the backend serves the built UI).
# Open the one url it prints:  http://127.0.0.1:8000
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- frontend: install + build (produces frontend/dist the backend serves) ---
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
[ -d dist ] || npm run build

# --- backend: venv + deps ---
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env

echo ""
echo "  MediaForge is running at  ->  http://127.0.0.1:8000"
echo "  (Ctrl+C to stop)"
echo ""

# One server serves both the UI and the API.
exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
