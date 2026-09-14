@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title SUNO 15SET MASTERING - INSTALL

echo ============================================================
echo SUNO 15SET MASTERING - FIRST TIME INSTALL
echo ============================================================
echo.

set "PY_CMD="

where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"

if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo Python was not found.
    echo.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Windows Package Manager ^(winget^) was not found.
        echo Install Python 3.12 from:
        echo https://www.python.org/downloads/windows/
        echo.
        echo Enable "Add python.exe to PATH" during setup.
        echo Then close this window and run START_HERE.bat again.
        pause
        exit /b 1
    )

    echo Installing Python 3.12 with winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo Python installation command finished.
    echo Close this window and run START_HERE.bat again.
    pause
    exit /b 0
)

echo Python found: %PY_CMD%
echo.

if exist ".venv\Scripts\python.exe" (
    echo Existing virtual environment found.
) else (
    echo [1/3] Creating virtual environment...
    %PY_CMD% -m venv ".venv"
    if errorlevel 1 goto :FAIL
)

echo [2/3] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :FAIL

echo [3/3] Installing FFmpeg helper...
".venv\Scripts\python.exe" -m pip install --upgrade imageio-ffmpeg
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo INSTALL COMPLETE
echo ============================================================
echo You can now run RUN.bat or START_HERE.bat.
echo.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo INSTALL FAILED
echo ============================================================
echo Take a screenshot of this window and send it to ChatGPT.
echo.
pause
exit /b 1
