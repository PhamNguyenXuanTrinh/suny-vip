@echo off
setlocal
cd /d "%~dp0app"
start "SUNNY ERP" "%~dp0runtime\windows\pythonw.exe" -m backend.scripts.desktop
