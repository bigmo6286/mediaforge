# One-shot setup for running MediaForge on a Windows machine with a CUDA GPU.
#   powershell -ExecutionPolicy Bypass -File setup_gpu.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"

Write-Host "==> Python venv + base deps"
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
& ".venv\Scripts\pip.exe" install -r requirements.txt

Write-Host "==> Checking for CUDA GPU"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    Write-Host "==> Installing GPU model stack (torch + diffusers). This is large."
    & ".venv\Scripts\pip.exe" install -r requirements-gpu.txt
} else {
    Write-Host "!! No nvidia-smi found - skipping GPU stack."
    Write-Host "   MediaForge will use hosted providers (add a key) or CPU editing/TTS."
}

Write-Host "==> Local voices for the avatar (Piper, CPU)"
& ".venv\Scripts\python.exe" -m piper.download_voices `
    en_US-amy-medium en_US-ryan-high en_GB-alba-medium --data-dir voices

Write-Host ""
Write-Host "Done. MediaForge auto-detects the GPU on startup."
& ".venv\Scripts\python.exe" -c "from app import config; print('  device =', config.DEVICE, '| default provider =', config.WAN_PROVIDER)"
Write-Host "Start it with:  powershell -ExecutionPolicy Bypass -File run.ps1"
