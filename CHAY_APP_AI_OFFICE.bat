@echo off
title AI Office - Che Do Ung Dung Desktop
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo     AI OFFICE - KHOI DONG CHE DO UNG DUNG (APP)
echo ===================================================
echo.

:: 1. Kiem tra Ollama
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo [*] Dang khoi dong Ollama ngam...
    start /b "" ollama serve >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: 2. Chay ung dung Native WebView
if exist "AI-Office.exe" (
    echo [*] Dang mo ung dung AI-Office.exe...
    start "" "AI-Office.exe"
) else (
    echo [*] Dang mo ung dung qua Python launcher...
    if exist ".venv\Scripts\pythonw.exe" (
        start "" ".venv\Scripts\pythonw.exe" app\launcher.py
    ) else (
        python app\launcher.py
    )
)
