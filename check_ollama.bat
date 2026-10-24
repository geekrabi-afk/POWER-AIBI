@echo off
setlocal
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%OLLAMA_EXE%" (
  "%OLLAMA_EXE%" list
) else (
  echo Ollama executable was not found at %OLLAMA_EXE%
)
powershell -NoProfile -Command "try { (Invoke-RestMethod http://localhost:11434/api/tags -TimeoutSec 3).models | Select-Object name } catch { Write-Host 'Ollama API is not responding. Start Ollama from the Start menu.' }"
pause

