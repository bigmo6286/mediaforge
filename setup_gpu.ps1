# One-shot GPU setup for MediaForge on Windows (NVIDIA CUDA).
# Installs the CUDA build of PyTorch + the model stack so generation runs
# locally with no API keys. Run this ONCE, then use run.ps1 as normal.
#   powershell -ExecutionPolicy Bypass -File setup_gpu.ps1
#
# CUDA channel: cu121 works for most recent NVIDIA drivers. Override if needed:
#   $env:TORCH_CUDA="cu124"; powershell -ExecutionPolicy Bypass -File setup_gpu.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$root\backend"
$cuda = if ($env:TORCH_CUDA) { $env:TORCH_CUDA } else { "cu124" }

function Find-Py {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 --version 2>$null; if ($LASTEXITCODE -eq 0) { return @("py","-3") } }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
    return $null
}

Write-Host "==> Checking for an NVIDIA GPU" -ForegroundColor Cyan
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
} else {
    Write-Host "!! nvidia-smi not found. This needs an NVIDIA GPU + driver." -ForegroundColor Yellow
    Write-Host "   (AMD/Intel GPUs are not supported by the CUDA build.)"
    Read-Host "Press Enter to continue anyway, or Ctrl+C to stop"
}

$pycmd = Find-Py
if (-not $pycmd) { Write-Host "ERROR: Python 3 not found. Install from python.org (Add to PATH)." -ForegroundColor Red; exit 1 }

Write-Host "==> Python venv + base deps" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { & $pycmd @("-m","venv",".venv") }
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

$pyver = & $py -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "==> Installing CUDA PyTorch (channel $cuda) for Python $pyver - large download" -ForegroundColor Cyan
& $py -m pip install torch torchvision --index-url "https://download.pytorch.org/whl/$cuda"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: no CUDA PyTorch wheel for Python $pyver on channel '$cuda'." -ForegroundColor Red
    Write-Host "Fix it any one of these ways:" -ForegroundColor Yellow
    Write-Host "  1) Try another CUDA channel, then rerun this script:"
    Write-Host "       `$env:TORCH_CUDA='cu126'   (or cu128 / cu121)"
    Write-Host "       Pick the one for your setup at https://pytorch.org/get-started/locally/"
    Write-Host "  2) Very new Python often has no wheels yet - Python 3.11 or 3.12 has the"
    Write-Host "     widest PyTorch support. Install one of those and rerun."
    Write-Host "  3) Or skip the GPU: the app runs fine on hosted providers (add a key in"
    Write-Host "     Settings) or on CPU for editing. Just use run.ps1."
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "==> Installing the model stack (diffusers, transformers, ...)" -ForegroundColor Cyan
& $py -m pip install -r requirements-gpu.txt

Write-Host "==> Local voice (Piper) - optional" -ForegroundColor Cyan
& $py -m pip install -r requirements-voice.txt
if ($LASTEXITCODE -eq 0) {
    & $py -m piper.download_voices en_US-amy-medium en_US-ryan-high en_GB-alba-medium --data-dir voices
}

Write-Host ""
Write-Host "==> Verifying GPU is visible to PyTorch" -ForegroundColor Cyan
& $py -c "import torch; ok=torch.cuda.is_available(); print('CUDA available:', ok); print('GPU:', torch.cuda.get_device_name(0) if ok else 'NONE - will fall back to hosted/CPU')"
& $py -c "from app import config; print('MediaForge device =', config.DEVICE, '| default provider =', config.WAN_PROVIDER)"

Write-Host ""
Write-Host "Done. If CUDA shows True above, start the app and it runs on your GPU:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File run.ps1"
Write-Host "If CUDA shows False, update your NVIDIA driver, or try TORCH_CUDA=cu124."
