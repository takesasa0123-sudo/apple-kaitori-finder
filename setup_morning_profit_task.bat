@echo off
setlocal
cd /d "%~dp0"
title Setup iPhone 18 Morning LINE Profit-Only Task

set SCHEDULE_TIME=08:00
if not "%~1"=="" set SCHEDULE_TIME=%~1

set TASK_NAME=iPhone18_Morning_Profit_Notify
set TARGET_BAT=%~dp0run_morning_profit.bat

echo =================================================================
echo   iPhone 18 Morning LINE Profit-Only - Task Scheduler Setup
echo =================================================================
echo.
echo Target Task Name : %TASK_NAME%
echo Schedule Time    : %SCHEDULE_TIME% (Daily)
echo Execution Script : %TARGET_BAT%
echo.

schtasks /create /tn "%TASK_NAME%" /tr "\"%TARGET_BAT%\"" /sc daily /st %SCHEDULE_TIME% /f

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Windows Task "%TASK_NAME%" registered successfully!
    echo It will send profit-only reports every day at %SCHEDULE_TIME%.
) else (
    echo.
    echo [ERROR] Failed to register task. Please try running as Administrator.
)

echo.
pause
