@echo off
setlocal
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not exist "%OLLAMA_EXE%" (
  echo Install Ollama first, then run this file again.
  pause
  exit /b 1
)
"%OLLAMA_EXE%" pull qwen2.5:3b
pause

