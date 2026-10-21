@echo off
setlocal
cd /d "%~dp0"
title Push Apple Kaitori Project to GitHub for Render Deployment

echo ====================================================================
echo   Apple Kaitori Profit Finder - Push to GitHub for Cloud Deployment
echo ====================================================================
echo.
echo Please create a new repository on GitHub (https://github.com/new).
echo Example: apple-kaitori-finder (Public or Private)
echo.
set /p REPO_URL="Enter your GitHub Repository URL: "

if "%REPO_URL%"=="" (
    echo [ERROR] Repository URL cannot be empty.
    pause
    exit /b 1
)

echo.
echo [1/3] Adding files to git...
git add .
git commit -m "Update for Render cloud deployment" 2>nul

echo [2/3] Setting remote repository: %REPO_URL%
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main

echo [3/3] Pushing to GitHub...
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Git push failed. Please check your GitHub URL or credentials.
    pause
    exit /b 1
)

echo.
echo ====================================================================
echo   SUCCESS! Pushed to GitHub successfully!
echo ====================================================================
echo Next step:
echo 1. Open Render dashboard: https://dashboard.render.com/
echo 2. Click "New" -^> "Web Service" -^> Connect your repository.
echo 3. Render will automatically detect render.yaml and deploy!
echo ====================================================================
echo.
pause
