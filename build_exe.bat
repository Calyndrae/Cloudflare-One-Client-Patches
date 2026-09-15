@echo off
title Build WarpFix.exe
setlocal

echo.
echo   Building a standalone WarpFix.exe ...
echo   (you only need this if you want to run the fix on a
echo    computer that does not have Python installed)
echo.

set PY=py -3
where py >nul 2>&1 || set PY=python

%PY% -m pip install --upgrade pyinstaller
if not "%errorlevel%"=="0" goto :failed

%PY% -m PyInstaller --onefile --uac-admin --name WarpFix "%~dp0warp_fix.py"
if not "%errorlevel%"=="0" goto :failed

echo.
echo   Done. Your file is here:  %~dp0dist\WarpFix.exe
echo.
pause
goto :end

:failed
echo.
echo   !! Build failed. Make sure Python is installed and on your PATH.
echo.
pause

:end
endlocal
