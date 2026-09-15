@echo off
title Cloudflare WARP Fix
setlocal

echo.
echo   ======================================================
echo    Cloudflare WARP Fix
echo    (for WARP stuck on "Connecting" / 26%%)
echo   ======================================================
echo.
echo   In a moment Windows will ask if this app can make
echo   changes to your device. Click YES.
echo.

where py >nul 2>&1
if "%errorlevel%"=="0" (
    py -3 "%~dp0warp_fix.py"
    goto :finished
)

where python >nul 2>&1
if "%errorlevel%"=="0" (
    python "%~dp0warp_fix.py"
    goto :finished
)

echo.
echo   !! Python was not found on this computer.
echo.
echo   1. Go to https://www.python.org/downloads/
echo   2. Download and open the installer.
echo   3. TICK the box "Add python.exe to PATH" before installing.
echo   4. Install, then double-click this file again.
echo.
pause

:finished
endlocal
