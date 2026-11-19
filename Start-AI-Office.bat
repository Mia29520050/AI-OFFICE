@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo AI Office environment is not installed yet.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "app\launcher.py" %*
