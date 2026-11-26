@echo off
title AI Office - Tat He Thong
chcp 65001 >nul

echo Dang dung toan bo may chu va tien trinh AI Office...

:: 1. Dung may chu web tren port 8765
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8765" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 2. Dong cac tien trinh webview va uvicorn
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im "AI-Office.exe" >nul 2>&1

:: 3. Dong tien trinh Chrome CDP cua AI Office tren port 9225 neu co
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":9225" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo [OK] Da dong toan bo AI Office an toan.
timeout /t 2 /nobreak >nul
