@echo off
title Cloudflare WARP Fix
setlocal EnableExtensions

rem ===========================================================================
rem  Cloudflare WARP Fix - one-file launcher.
rem
rem  This is the ONLY file you need to download. It will, in order:
rem    1. ask Windows for administrator rights (WARP runs as a service),
rem    2. install Python for you if it is not already on this computer,
rem    3. download warp_fix.py if it is not sitting next to this file,
rem    4. run the fix.
rem ===========================================================================

set "REPO_RAW=https://raw.githubusercontent.com/Calyndrae/Cloudflare-One-Client-Patches/HEAD"
set "PY_VERSION=3.13.7"
set "SELF=%~f0"
set "SELFDIR=%~dp0"
set "SELFARGS=%*"

echo.
echo   ======================================================
echo    Cloudflare WARP Fix
echo    (for WARP stuck on "Connecting" / 26%%)
echo   ======================================================
echo.

rem --------------------------------------------------------------------------
rem  1. Administrator rights
rem --------------------------------------------------------------------------
net session >nul 2>&1
if not errorlevel 1 goto :is_admin

echo   Windows is about to ask if this app can make changes to
echo   your device. Click YES.
echo.
if defined SELFARGS goto :elevate_with_args
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath $env:SELF -Verb RunAs -WorkingDirectory $env:SELFDIR" >nul 2>&1
goto :elevate_done

:elevate_with_args
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath $env:SELF -Verb RunAs -ArgumentList $env:SELFARGS -WorkingDirectory $env:SELFDIR" >nul 2>&1

:elevate_done
if errorlevel 1 (
    echo.
    echo   !! Administrator rights were refused, so nothing was changed.
    echo      Right-click this file and pick "Run as administrator".
    echo.
    pause
)
exit /b 0

:is_admin

rem --------------------------------------------------------------------------
rem  2. Python
rem --------------------------------------------------------------------------
call :find_python
if defined PYCMD goto :have_python

echo   Python is not installed. Installing it now - this takes a
echo   couple of minutes and needs an internet connection.
echo.

call :install_python_winget
call :find_python
if defined PYCMD goto :have_python

call :install_python_download
call :find_python
if defined PYCMD goto :have_python

echo.
echo   !! Could not install Python automatically.
echo.
echo      Install it by hand instead:
echo        1. Go to https://www.python.org/downloads/
echo        2. Download and open the installer.
echo        3. TICK "Add python.exe to PATH" before installing.
echo        4. Double-click this file again.
echo.
pause
exit /b 1

:have_python
echo   Python: %PYCMD% %PYARGS%

rem --------------------------------------------------------------------------
rem  3. The fix script
rem --------------------------------------------------------------------------
set "SCRIPT=%SELFDIR%warp_fix.py"
if exist "%SCRIPT%" goto :have_script

set "SCRIPT=%TEMP%\warp_fix.py"
echo   Downloading warp_fix.py ...
call :download "%REPO_RAW%/warp_fix.py" "%SCRIPT%"
if exist "%SCRIPT%" goto :have_script

echo.
echo   !! Could not download warp_fix.py.
echo      Check your internet connection, or download warp_fix.py from
echo      https://github.com/Calyndrae/Cloudflare-One-Client-Patches
echo      and put it in the same folder as this file.
echo.
pause
exit /b 1

:have_script
echo   Script: %SCRIPT%
echo.

rem --------------------------------------------------------------------------
rem  4. Run it (we are already elevated, so tell it not to ask again)
rem --------------------------------------------------------------------------
set "EXTRA="

:run_fix
"%PYCMD%" %PYARGS% "%SCRIPT%" --no-elevate --no-pause %EXTRA% %SELFARGS%
set "RC=%errorlevel%"

rem  The script tells us what is worth offering next:
rem    5 = other VPN / proxy software is in the way and can be cleared
rem    2 = not fixed, machine in one piece, the protocol is the last idea
rem  Both change things on this PC, so both are asked rather than assumed.
if "%RC%"=="5" goto :offer_clean
if "%RC%"=="2" goto :offer_protocol
goto :done

:offer_clean
echo %EXTRA% %SELFARGS% | find /i "--clean-tun" >nul
if not errorlevel 1 goto :offer_protocol
echo.
echo   Other VPN / proxy software is standing in WARP's way - the
echo   details are listed above. This can stop those programs, switch
echo   off their tunnel adapters and clear the system proxy.
echo.
echo   It is reversible: everything is written down first, and
echo   RUN_ME.bat --restore-tun puts all of it back. If the cleanup
echo   takes this PC off the internet, it undoes itself immediately.
echo.
set "ANSWER="
set /p "ANSWER=  Clear them out of the way now? [y/N] "
if /i not "%ANSWER%"=="y" goto :offer_protocol
set "EXTRA=%EXTRA% --clean-tun"
echo.
goto :run_fix

:offer_protocol
echo %EXTRA% %SELFARGS% | find /i "--try-protocols" >nul
if not errorlevel 1 goto :done
echo.
echo   One thing is left to try: WARP can tunnel over MASQUE or over
echo   WireGuard, and some networks allow one but block the other.
echo   Your current setting is put straight back if the other one does
echo   not connect either.
echo.
set "ANSWER="
set /p "ANSWER=  Try the other tunnel protocol now? [y/N] "
if /i not "%ANSWER%"=="y" goto :done
set "EXTRA=%EXTRA% --try-protocols"
echo.
goto :run_fix

:done
echo.
pause
exit /b %RC%


rem ===========================================================================
rem  subroutines
rem ===========================================================================

:find_python
rem Sets PYCMD (+ PYARGS) to something runnable, or leaves them empty.
set "PYCMD="
set "PYARGS="

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYCMD=py"
    set "PYARGS=-3"
    exit /b 0
)

rem `python` on a clean Windows is often the Microsoft Store stub, which is not
rem a real interpreter - skip anything under WindowsApps.
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
rem %1 = url, %2 = destination. Passed through the environment so that neither
rem cmd nor powershell has to re-quote them.
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
