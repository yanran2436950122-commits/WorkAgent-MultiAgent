@echo off
cd /d "%~dp0"
powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0run_local.ps1"
pause
