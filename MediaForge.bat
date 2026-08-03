@echo off
REM Double-click this file to start MediaForge on Windows.
title MediaForge
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0run.ps1"
echo.
echo MediaForge has stopped. You can close this window.
pause >nul
