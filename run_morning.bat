@echo off
setlocal
cd /d "%~dp0"
title iPhone 18 Morning LINE Notifier

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH.
    pause
    exit /b 1
)

echo [iPhone 18 Morning LINE Notifier] Running daily price check...
python main.py --line-notify

if %errorlevel% neq 0 (
    echo [ERROR] Script execution failed with code %errorlevel%.
) else (
    echo [SUCCESS] Morning price check and LINE notification completed.
)
