# Creates a double-click "MediaForge" shortcut on your Desktop (run once).
#   powershell -ExecutionPolicy Bypass -File Create-Desktop-Shortcut.ps1
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'MediaForge.lnk'

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = Join-Path $root 'MediaForge.bat'
$lnk.WorkingDirectory = $root
$lnk.IconLocation = 'shell32.dll,220'   # a small film/clip icon
$lnk.Description = 'Launch MediaForge'
$lnk.Save()

Write-Host ""
Write-Host "Done. A 'MediaForge' icon is now on your Desktop." -ForegroundColor Green
Write-Host "Double-click it any time to start the app."
