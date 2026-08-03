#!/usr/bin/env bash
# One-shot setup for running MediaForge locally on a CUDA GPU machine.
# After this, everything (LTX/Wan motion, avatar, TTS) runs on-device — no keys.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"

echo "==> Python venv + base deps"
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> Checking for CUDA GPU"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
  echo "==> Installing GPU model stack (torch + diffusers). This is large."
  ./.venv/bin/pip install -r requirements-gpu.txt
else
  echo "!! No nvidia-smi found — skipping GPU stack."
  echo "   MediaForge will use hosted providers (add a key) or CPU editing/TTS."
fi

echo "==> Local voices for the avatar (Piper, CPU)"
./.venv/bin/python -m piper.download_voices \
  en_US-amy-medium en_US-ryan-high en_GB-alba-medium --data-dir voices || true

echo ""
echo "Done. MediaForge auto-detects the GPU on startup:"
./.venv/bin/python -c "from app import config; print('  device =', config.DEVICE, '| default provider =', config.WAN_PROVIDER)"
echo ""
echo "Start it with:  ./run.sh    (UI at http://localhost:5173)"
echo "For local talking-avatar, also clone SadTalker and set SADTALKER_DIR"
echo "(see README). Motion + TTS work without it."
