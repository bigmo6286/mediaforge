# Start MediaForge on Windows as a SINGLE server (backend serves the UI).
# Open the ONE url it prints:  http://127.0.0.1:8000
#   powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Step($n, $total, $msg) {
    Write-Host ""
    Write-Host "==> [$n/$total] $msg" -ForegroundColor Cyan
}

Write-Host "MediaForge setup — first run installs packages and can take a few minutes." -ForegroundColor Yellow

# --- 1/4 frontend deps ---
Set-Location "$root\frontend"
Step 1 4 "Installing frontend packages (npm)..."
if (Test-Path "node_modules") {
    Write-Host "    already installed, skipping."
} else {
    npm install   # npm prints its own progress
}

# --- 2/4 build UI ---
Step 2 4 "Building the web UI..."
npm run build

# --- 3/4 backend deps ---
Set-Location "$root\backend"
Step 3 4 "Setting up Python environment (pip)..."
if (-not (Test-Path ".venv")) { python -m venv .venv }
Write-Host "    installing Python packages (progress shown below)..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\pip.exe" install -r requirements.txt   # no -q: shows progress
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

# --- 4/4 start ---
Step 4 4 "Starting MediaForge..."
Write-Host ""
Write-Host "  ✓ Ready — open  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  (Ctrl+C to stop)"
Write-Host ""
Start-Process "http://127.0.0.1:8000"
& ".venv\Scripts\uvicorn.exe" "app.main:app" --host 127.0.0.1 --port 8000
