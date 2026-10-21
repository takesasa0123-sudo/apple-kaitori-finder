@echo off
setlocal
cd /d "%~dp0"
title Build Android APK - Apple Kaitori Profit Finder

set "PATH=%PATH%;C:\Users\User\AppData\Local\Programs\nodejs"

echo ====================================================================
echo   Android APK Builder (React Native / Expo EAS Build)
echo ====================================================================
echo.
echo [Step 1/3] Updating latest Apple Store and Kaitori price snapshot...
python mobile_server.py

echo.
echo [Step 2/3] Installing React Native (Expo) dependencies...
cd /d "%~dp0mobile-app"
if not exist "node_modules" (
    call npm install
)

echo.
echo [Step 3/3] Starting EAS Android APK Build...
echo (Note: If prompted, log in with a free Expo account at https://expo.dev)
echo (Once completed, a direct download URL and QR code for the .apk file will appear!)
echo.
call npx eas-cli build -p android --profile apk

echo.
pause
