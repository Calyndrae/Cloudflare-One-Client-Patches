@echo off
title Build WarpFix.exe
setlocal EnableExtensions

rem ===========================================================================
rem  Builds dist\WarpFix.exe - a standalone, self-elevating copy of the fix for
rem  machines that have no internet access or no Python.
rem
rem  Most people do NOT need this. Just run RUN_ME.bat instead.
rem
rem  Everything this needs (Python, pip, PyInstaller) is installed for you.
rem ===========================================================================

set "PY_VERSION=3.13.7"

echo.
echo   Building a standalone WarpFix.exe ...
echo.

rem --------------------------------------------------------------------------
rem  Python
rem --------------------------------------------------------------------------
call :find_python
if defined PYCMD goto :have_python

echo   Python is not installed. Installing it now ...
call :install_python_winget
call :find_python
if defined PYCMD goto :have_python

call :install_python_download
call :find_python
if defined PYCMD goto :have_python

echo.
echo   !! Could not install Python automatically. Install it from
echo      https://www.python.org/downloads/ (tick "Add python.exe to PATH")
echo      and run this file again.
echo.
pause
exit /b 1

:have_python
echo   Python: %PYCMD% %PYARGS%
echo.

rem --------------------------------------------------------------------------
rem  PyInstaller
rem --------------------------------------------------------------------------
echo   Installing / updating PyInstaller ...
"%PYCMD%" %PYARGS% -m pip install --upgrade pip >nul 2>&1
"%PYCMD%" %PYARGS% -m pip install --upgrade pyinstaller
if errorlevel 1 goto :failed

rem --------------------------------------------------------------------------
rem  Build
rem --------------------------------------------------------------------------
echo.
echo   Building ...
"%PYCMD%" %PYARGS% -m PyInstaller --onefile --uac-admin --name WarpFix "%~dp0warp_fix.py"
if errorlevel 1 goto :failed

echo.
echo   Done. Your file is here:  %~dp0dist\WarpFix.exe
echo.
pause
exit /b 0

:failed
echo.
echo   !! Build failed. See the messages above.
echo.
pause
exit /b 1


rem ===========================================================================
rem  subroutines (kept in step with RUN_ME.bat)
rem ===========================================================================

:find_python
set "PYCMD="
set "PYARGS="

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYCMD=py"
    set "PYARGS=-3"
    exit /b 0
)

for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | find /i "\WindowsApps\" >nul
    if errorlevel 1 if not defined PYCMD set "PYCMD=%%I"
)
if defined PYCMD exit /b 0

set "PF86=%ProgramFiles(x86)%"
for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%~D\python.exe" set "PYCMD=%%~D\python.exe"
)
for /d %%D in ("%PF86%\Python3*") do (
    if exist "%%~D\python.exe" set "PYCMD=%%~D\python.exe"
)
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%~D\python.exe" set "PYCMD=%%~D\python.exe"
)
if defined PYCMD exit /b 0

if exist "%SystemRoot%\py.exe" (
    set "PYCMD=%SystemRoot%\py.exe"
    set "PYARGS=-3"
)
exit /b 0


:install_python_winget
where winget >nul 2>&1
if errorlevel 1 exit /b 1
echo   Trying winget ...
winget install --exact --id Python.Python.3.13 --scope machine --silent ^
    --accept-source-agreements --accept-package-agreements ^
    --disable-interactivity >nul 2>&1
exit /b 0


:install_python_download
set "PY_ARCH=amd64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PY_ARCH=arm64"
set "PY_SETUP=%TEMP%\python-%PY_VERSION%-%PY_ARCH%.exe"

echo   Downloading Python %PY_VERSION% from python.org ...
call :download "https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-%PY_ARCH%.exe" "%PY_SETUP%"
if not exist "%PY_SETUP%" exit /b 1

echo   Installing Python (quietly) ...
"%PY_SETUP%" /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_test=0
del /q "%PY_SETUP%" >nul 2>&1
exit /b 0


:download
set "DL_URL=%~1"
set "DL_OUT=%~2"
del /q "%DL_OUT%" >nul 2>&1

where curl >nul 2>&1
if not errorlevel 1 (
    curl -fsSL -o "%DL_OUT%" "%DL_URL%"
    if exist "%DL_OUT%" exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri $env:DL_URL -OutFile $env:DL_OUT -UseBasicParsing" >nul 2>&1
exit /b 0
