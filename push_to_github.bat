@echo off
setlocal
cd /d "%~dp0"
title Push Apple Kaitori Project to GitHub for Render Deployment

set "DEFAULT_REPO=https://github.com/takesasa0123-sudo/apple-kaitori-finder.git"

echo ====================================================================
echo   Apple Kaitori Profit Finder - Push to GitHub for Cloud Deployment
echo ====================================================================
echo.
echo Target GitHub Repository:
echo   %DEFAULT_REPO%
echo.
echo Press Enter to push to this repository, or enter another URL.
set /p REPO_URL="Repository URL (Just press Enter to use default): "

if "%REPO_URL%"=="" set "REPO_URL=%DEFAULT_REPO%"

echo.
echo [1/3] Adding files to git...
git add .
git commit -m "Update for Render cloud deployment" 2>nul

echo [2/3] Setting remote repository: %REPO_URL%
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git branch -M main

echo [3/3] Pushing to GitHub...
echo (If a GitHub login browser window pops up, please click "Authorize" or log in)
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Git push failed. Please check your GitHub credentials or connection.
    pause
    exit /b 1
)

echo.
echo ====================================================================
echo   SUCCESS! Pushed to GitHub successfully!
echo ====================================================================
echo Next step:
echo Go back to your Render dashboard and click "Manual Deploy" -> "Deploy latest commit"!
echo ====================================================================
echo.
pause
