@echo off
setlocal
cd /d "%~dp0"
py -3.11 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo.
echo Setup complete. Run run_dashboard.bat to start the dashboard.
pause
exit /b 0
:fail
echo Setup failed. Check that Python 3.11 is installed and internet is available for the first installation.
pause
exit /b 1

