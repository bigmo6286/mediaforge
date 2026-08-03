# Start MediaForge on Windows as a SINGLE server (backend serves the UI).
# Open the ONE url it prints:  http://127.0.0.1:8000
#   powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- frontend: install + build (produces frontend/dist the backend serves) ---
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
if (-not (Test-Path "dist")) { npm run build }

# --- backend: venv + deps ---
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    & ".venv\Scripts\pip.exe" install -q -r requirements.txt
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host ""
Write-Host "  MediaForge is running at  ->  http://127.0.0.1:8000"
Write-Host "  (Ctrl+C to stop)"
Write-Host ""
Start-Process "http://127.0.0.1:8000"

# One server serves both the UI and the API.
& ".venv\Scripts\uvicorn.exe" "app.main:app" --host 127.0.0.1 --port 8000
