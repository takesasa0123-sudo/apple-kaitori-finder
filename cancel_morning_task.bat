@echo off
setlocal
cd /d "%~dp0"
title Cancel iPhone 18 Morning LINE Task

set TASK_NAME=iPhone18_Morning_Price_Notify

echo ========================================================
echo   iPhone 18 Morning LINE Notify - Task Scheduler Removal
echo ========================================================
echo Removing Windows Scheduled Tasks...
echo.

schtasks /delete /tn "iPhone18_Morning_Price_Notify" /f >nul 2>nul
if %errorlevel% equ 0 (
    echo [SUCCESS] Task "iPhone18_Morning_Price_Notify" deleted.
) else (
    echo [INFO] Task "iPhone18_Morning_Price_Notify" was not found.
)

schtasks /delete /tn "iPhone18_Morning_Profit_Notify" /f >nul 2>nul
if %errorlevel% equ 0 (
    echo [SUCCESS] Task "iPhone18_Morning_Profit_Notify" deleted.
) else (
    echo [INFO] Task "iPhone18_Morning_Profit_Notify" was not found.
)

echo.
pause
