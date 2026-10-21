@echo off
setlocal
cd /d "%~dp0"
title Apple Kaitori Mobile App Launcher (iPhone and Android)

set "PATH=%PATH%;C:\Users\User\AppData\Local\Programs\nodejs"

echo ====================================================================
echo   Apple Kaitori Profit Finder - Mobile App Launcher
echo ====================================================================
echo.
echo   [1] Start Mobile App Server and Open App (Instant iPhone/Android/PC)
echo   [2] Start React Native Expo Go Server (QR Code for Expo Go App)
echo   [3] Build Standalone Android .apk File (EAS Build)
echo.
set /p MODE="Select mode [1-3, default: 1]: "

if "%MODE%"=="2" (
    python mobile_server.py
    cd /d "%~dp0mobile-app"
    if not exist "node_modules" (
        echo Installing npm packages...
        call npm install
    )
    call npx expo start
    pause
    exit /b 0
)

if "%MODE%"=="3" (
    call "%~dp0build_apk.bat"
    exit /b 0
)

python mobile_server.py --serve --open
pause
