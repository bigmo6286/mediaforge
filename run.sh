#!/usr/bin/env bash
# Start MediaForge as a SINGLE server (the backend serves the built UI).
# Open the one url it prints:  http://127.0.0.1:8000
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

step() { printf "\n==> [%s/4] %s\n" "$1" "$2"; }

echo "MediaForge setup — first run installs packages and can take a few minutes."

# --- 1/4 frontend deps ---
cd "$ROOT/frontend"
step 1 "Installing frontend packages (npm)..."
if [ -d node_modules ]; then echo "    already installed, skipping."; else npm install; fi

# --- 2/4 build UI ---
step 2 "Building the web UI..."
npm run build

# --- 3/4 backend deps ---
cd "$ROOT/backend"
step 3 "Setting up Python environment (pip)..."
[ -d .venv ] || python3 -m venv .venv
echo "    installing Python packages (progress shown below)..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt   # no -q: shows progress
[ -f .env ] || cp .env.example .env

# Optional local voice (Piper) — best effort, never blocks the app.
echo "    installing local voice (Piper, optional)..."
if ./.venv/bin/pip install -r requirements-voice.txt; then
  ls voices/*.onnx >/dev/null 2>&1 || \
    ./.venv/bin/python -m piper.download_voices en_US-amy-medium en_US-ryan-high --data-dir voices || true
else
  echo "    (Piper voice unavailable on this system — avatar will use hosted TTS.)"
fi

# --- 4/4 start ---
step 4 "Starting MediaForge..."
echo ""
echo "  ✓ Ready — open  http://127.0.0.1:8000"
echo "  (Ctrl+C to stop)"
echo ""
exec ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
