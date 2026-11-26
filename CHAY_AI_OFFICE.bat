@echo off
title AI Office - Khoi Dong He Thong
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo           AI OFFICE - HE THONG AI CUC BO
echo ===================================================
echo.

:: 1. Kiem tra va khoi dong Ollama neu chua chay
echo [1/3] Kiem tra mo hinh AI Ollama...
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo [*] Dang khoi dong Ollama ngam...
    start /b "" ollama serve >nul 2>&1
    timeout /t 2 /nobreak >nul
) else (
    echo [OK] Ollama dang chay san sang.
)

:: 2. Chon Python phu hop
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

:: 3. Mo trinh duyet vao giao dien
echo [2/3] Dang mo trinh duyet web...
start "" "http://localhost:8765"

echo [3/3] Dang chay May chu AI Office tren Port 8765...
echo.
echo ===================================================
echo  AI Office dang hoat dong tai:
echo    - May tinh (PC):     http://localhost:8765
echo    - Dien thoai (LAN):  http://192.168.1.2:8765
echo    - Thu muc xuat file: F:\AI-Office\Export
echo.
echo  De chay khong hien terminal: Chay CHAY_AI_OFFICE_AN_TERMINAL.vbs
echo  De tat he thong: Nhan Ctrl+C hoac dong cua so nay.
echo ===================================================
echo.

%PY_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 8765
pause
