@echo off
title AI Office - Che Do Trinh Duyet Web
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo     AI OFFICE - KHOI DONG CHE DO WEB BROWSER
echo ===================================================
echo.

:: 1. Kiem tra Ollama
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo [*] Dang khoi dong Ollama ngam...
    start /b "" ollama serve >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: 2. Chon Python phu hop
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

:: 3. Mo trinh duyet vao giao dien
echo [*] Dang mo trinh duyet web...
start "" "http://localhost:8765"

echo [*] May chu dang hoat dong tren port 8765. Nhan Ctrl+C de dung.
%PY_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 8765
pause
