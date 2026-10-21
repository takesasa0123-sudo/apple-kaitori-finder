@echo off
setlocal
cd /d "%~dp0"
title iPhone 18 Kaitori Tracker

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python or add it to your system PATH.
    pause
    exit /b 1
)

echo [1/2] Checking required packages...
pip install -r requirements.txt --quiet

echo [2/2] Launching iPhone 18 Tracker...
echo.

if "%~1"=="" (
    python main.py --menu
) else (
    python main.py %*
)

echo.
pause
