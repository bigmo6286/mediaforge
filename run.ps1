# Start MediaForge on Windows as a SINGLE server (backend serves the UI).
# Open the ONE url it prints:  http://127.0.0.1:8000
#   powershell -ExecutionPolicy Bypass -File run.ps1
#
# We DON'T set $ErrorActionPreference=Stop globally, because npm/pip write
# harmless warnings to stderr; instead we check each command's exit code.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Step($n, $msg) {
    Write-Host ""
    Write-Host "==> [$n/4] $msg" -ForegroundColor Cyan
}
function Fail($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
function CheckExit($what) {
    if ($LASTEXITCODE -ne 0) { Fail "$what failed (exit $LASTEXITCODE). See the output above." }
}

Write-Host "MediaForge setup — first run installs packages and can take a few minutes." -ForegroundColor Yellow

# --- locate Node/npm ---
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Fail "Node.js / npm not found. Install Node.js LTS from https://nodejs.org and reopen PowerShell."
}

# --- locate a real Python 3 (prefer the 'py' launcher; avoid the Store stub) ---
$PY = $null; $PYARGS = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 --version 2>$null; if ($LASTEXITCODE -eq 0) { $PY = "py"; $PYARGS = @("-3") }
}
if (-not $PY -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $ver = & python --version 2>&1
    if ($LASTEXITCODE -eq 0 -and "$ver" -match "Python 3") { $PY = "python" }
}
if (-not $PY) {
    Fail ("Python 3 not found (or the Microsoft Store stub is in the way). Install " +
          "Python 3.10+ from https://www.python.org/downloads/windows/ and tick " +
          "'Add python.exe to PATH', then reopen PowerShell.")
}

# --- 1/4 frontend deps ---
Set-Location "$root\frontend"
Step 1 "Installing frontend packages (npm)..."
if (Test-Path "node_modules") { Write-Host "    already installed, skipping." }
else { npm install; CheckExit "npm install" }

# --- 2/4 build UI ---
Step 2 "Building the web UI..."
npm run build; CheckExit "npm run build"

# --- 3/4 backend deps ---
Set-Location "$root\backend"
Step 3 "Setting up Python environment (pip)..."
if (-not (Test-Path ".venv")) { & $PY @PYARGS -m venv .venv; CheckExit "python -m venv" }
if (-not (Test-Path ".venv\Scripts\python.exe")) { Fail "venv was not created (.venv\Scripts\python.exe missing)." }
Write-Host "    installing Python packages (progress shown below)..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt; CheckExit "pip install"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

# Optional local voice (Piper) — best effort, never blocks the app.
Write-Host "    installing local voice (Piper, optional)..."
& ".venv\Scripts\python.exe" -m pip install -r requirements-voice.txt
if ($LASTEXITCODE -eq 0) {
    if (-not (Test-Path "voices\*.onnx")) {
        & ".venv\Scripts\python.exe" -m piper.download_voices en_US-amy-medium en_US-ryan-high --data-dir voices 2>$null
    }
} else {
    Write-Host "    (Piper voice unavailable on this system — avatar will use hosted TTS.)" -ForegroundColor Yellow
}

# --- 4/4 start ---
Step 4 "Starting MediaForge..."
Write-Host ""
Write-Host "  Ready — open  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  (Ctrl+C to stop)"
Write-Host ""
Start-Process "http://127.0.0.1:8000"
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
