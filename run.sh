#!/usr/bin/env bash
# Start the MediaForge backend + frontend together.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- backend ---
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACK_PID=$!

# --- frontend ---
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run dev &
FRONT_PID=$!

echo ""
echo "  MediaForge is starting…"
echo "  UI:  http://localhost:5173"
echo "  API: http://127.0.0.1:8000"
echo "  (Ctrl+C to stop both)"
echo ""

trap "kill $BACK_PID $FRONT_PID 2>/dev/null" EXIT
wait
