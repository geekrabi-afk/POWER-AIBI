@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\streamlit.exe (
  echo Dependencies are missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m streamlit run app.py --server.headless false --browser.gatherUsageStats false

