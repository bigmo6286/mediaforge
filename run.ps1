# Start MediaForge (backend + frontend) on Windows.
#   Right-click > Run with PowerShell, or:  powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- backend ---
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    & ".venv\Scripts\pip.exe" install -q -r requirements.txt
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
$backend = Start-Process -PassThru -NoNewWindow `
    ".venv\Scripts\uvicorn.exe" "app.main:app --host 127.0.0.1 --port 8000"

# --- frontend ---
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
$frontend = Start-Process -PassThru -NoNewWindow "npm" "run dev"

Write-Host ""
Write-Host "  MediaForge is starting..."
Write-Host "  UI:  http://localhost:5173"
Write-Host "  API: http://127.0.0.1:8000"
Write-Host "  (Close this window or press Ctrl+C to stop)"
Write-Host ""

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id, $frontend.Id -ErrorAction SilentlyContinue
}
