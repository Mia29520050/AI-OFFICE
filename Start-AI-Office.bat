@echo off
cd /d "%~dp0"
if exist "AI-Office.exe" (
  start "" "%~dp0AI-Office.exe" %*
  exit /b 0
)
if exist "Start-AI-Office.vbs" (
  start "" wscript.exe //B "Start-AI-Office.vbs" %*
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo AI Office environment is not installed yet.
  pause
  exit /b 1
)
start "" /B ".venv\Scripts\pythonw.exe" "app\launcher.py" %*
exit /b 0
