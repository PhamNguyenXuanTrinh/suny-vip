@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.lock.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m backend.scripts.setup_local
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m backend.scripts.run_server --open-browser
if errorlevel 1 goto fail
exit /b 0
:fail
echo Khong khoi dong duoc. Hay kiem tra thong bao phia tren.
pause
exit /b 1
