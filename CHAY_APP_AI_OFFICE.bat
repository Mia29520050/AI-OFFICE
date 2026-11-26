@echo off
title AI Office - Che Do Ung Dung Desktop
chcp 65001 >nul
cd /d "%~dp0"

if exist "AI-Office.exe" (
    start "" "AI-Office.exe"
) else (
    if exist ".venv\Scripts\pythonw.exe" (
        start "" ".venv\Scripts\pythonw.exe" app\launcher.py
    ) else (
        start "" pythonw app\launcher.py
    )
)
