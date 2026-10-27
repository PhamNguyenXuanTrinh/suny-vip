@echo off
setlocal
set PYTHONUTF8=1
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0runtime\windows\python.exe" "%~dp0app\deploy\install_windows.py" --source "%~dp0."
if errorlevel 1 goto fail
echo Da cai SUNNY ERP. Mo bieu tuong SUNNY ERP tren Desktop de su dung.
pause
exit /b 0
:fail
echo Chua cai duoc. Hay giu thong bao loi de ky thuat kiem tra.
pause
exit /b 1
