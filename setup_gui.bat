@echo off
chcp 65001 >/dev/null
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0setup_gui.ps1"
pause
