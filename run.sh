#!/usr/bin/env bash
# Start MediaForge as a SINGLE server (the backend serves the built UI).
# Open the one url it prints:  http://127.0.0.1:8000
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

step() { printf "\n==> [%s/4] %s\n" "$1" "$2"; }

echo "MediaForge setup - first run installs packages and can take a few minutes."

# --- 1-2/4 frontend UI ---
# The prebuilt UI (frontend/dist) ships in the repo, so Node is NOT needed just
# to run the app. Only build if dist is missing (e.g. you changed the frontend).
if [ -f "$ROOT/frontend/dist/index.html" ]; then
  step 1 "Web UI already built - skipping (no Node needed)."
  step 2 "(build skipped)"
elif command -v npm >/dev/null 2>&1; then
  cd "$ROOT/frontend"
  step 1 "Installing frontend packages (npm)..."
  [ -d node_modules ] && echo "    already installed, skipping." || npm install
  step 2 "Building the web UI..."
  npm run build
else
  echo "ERROR: the web UI isn't built and npm isn't installed. Get a copy that"
  echo "includes frontend/dist (git pull), or install Node.js from https://nodejs.org"
  exit 1
fi

# --- 3/4 backend deps ---
cd "$ROOT/backend"
step 3 "Setting up Python environment (pip)..."
[ -d .venv ] || python3 -m venv .venv
echo "    installing Python packages (progress shown below)..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt   # no -q: shows progress
[ -f .env ] || cp .env.example .env

# Optional local voice (Piper) - best effort, never blocks the app.
echo "    installing local voice (Piper, optional)..."
if ./.venv/bin/pip install -r requirements-voice.txt; then
  ls voices/*.onnx >/dev/null 2>&1 || \
    ./.venv/bin/python -m piper.download_voices en_US-amy-medium en_US-ryan-high --data-dir voices || true
else
  echo "    (Piper voice unavailable on this system - avatar will use hosted TTS.)"
fi

# --- 4/4 start ---
step 4 "Starting MediaForge..."

# Free port 8000 if a previous MediaForge instance is still running on it.
OLD_PID=$(ss -ltnp 2>/dev/null | grep ':8000 ' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
if [ -n "$OLD_PID" ]; then
  echo "    stopping a previous server on port 8000 (PID $OLD_PID)..."
  kill "$OLD_PID" 2>/dev/null || true
  sleep 1
fi

echo ""
echo "  Ready - open  http://127.0.0.1:8000"
echo "  (Ctrl+C to stop)"
echo ""
exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
