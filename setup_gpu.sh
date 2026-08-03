#!/usr/bin/env bash
# One-shot GPU setup for MediaForge (NVIDIA CUDA). Installs the CUDA build of
# PyTorch + the model stack so generation runs locally with no API keys.
# Run once, then use ./run.sh as normal.
#
# CUDA channel: cu121 suits most recent drivers. Override: TORCH_CUDA=cu124 ./setup_gpu.sh
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/backend"
CUDA="${TORCH_CUDA:-cu121}"

echo "==> Checking for an NVIDIA GPU"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
else
  echo "!! nvidia-smi not found. The CUDA build needs an NVIDIA GPU + driver."
  echo "   (AMD/Intel GPUs are not supported here.)"
fi

echo "==> Python venv + base deps"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> Installing CUDA PyTorch ($CUDA) - large download"
./.venv/bin/pip install torch torchvision --index-url "https://download.pytorch.org/whl/$CUDA"

echo "==> Installing the model stack (diffusers, transformers, ...)"
./.venv/bin/pip install -r requirements-gpu.txt

echo "==> Local voice (Piper) - optional"
if ./.venv/bin/pip install -r requirements-voice.txt; then
  ./.venv/bin/python -m piper.download_voices \
    en_US-amy-medium en_US-ryan-high en_GB-alba-medium --data-dir voices || true
fi

echo ""
echo "==> Verifying GPU is visible to PyTorch"
./.venv/bin/python -c "import torch; ok=torch.cuda.is_available(); print('CUDA available:', ok); print('GPU:', torch.cuda.get_device_name(0) if ok else 'NONE - will fall back to hosted/CPU')"
./.venv/bin/python -c "from app import config; print('MediaForge device =', config.DEVICE, '| default provider =', config.WAN_PROVIDER)"

echo ""
echo "Done. If CUDA shows True above, start the app and it runs on your GPU:"
echo "  ./run.sh"
echo "If CUDA shows False, update your NVIDIA driver, or try TORCH_CUDA=cu124."
