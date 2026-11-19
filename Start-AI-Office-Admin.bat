@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if not exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  echo AI Office environment is not installed yet.
  pause
  exit /b 1
)
powershell -NoProfile -Command "Start-Process -FilePath ($env:ROOT + '\.venv\Scripts\pythonw.exe') -ArgumentList @($env:ROOT + '\app\launcher.py', '--allow-elevated') -WorkingDirectory $env:ROOT -Verb RunAs"
