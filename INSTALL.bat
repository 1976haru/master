@echo off
setlocal EnableExtensions
cd /d "%~dp0"

chcp 65001 >nul
set "PYTHONUTF8=1"

title HARU SUNO 15SET MASTERING - INSTALL

echo ============================================================
echo HARU / SUNO 15SET MASTERING v3.6.1 - BASE INSTALL
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
    echo [1/12] Creating virtual environment...
    %PY_CMD% -m venv ".venv"
    if errorlevel 1 goto :FAIL
)

echo [2/12] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :FAIL

echo [3/12] Installing FFmpeg helper and audio analysis libraries...
".venv\Scripts\python.exe" -m pip install --upgrade imageio-ffmpeg numpy scipy soundfile pyloudnorm
if errorlevel 1 goto :FAIL

echo [4/12] Installing HARU Mastering v3.6.1 core from this folder...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :FAIL

echo [5/12] Verifying v3 feature core...
".venv\Scripts\python.exe" .\scripts\verify_v3_features.py
if errorlevel 1 goto :FAIL

echo [6/12] Verifying v3 runtime adapter...
".venv\Scripts\python.exe" .\scripts\verify_v3_app.py
if errorlevel 1 goto :FAIL

echo [7/12] Verifying v3.2 auto-finish adapter...
".venv\Scripts\python.exe" .\scripts\verify_v31_app.py
if errorlevel 1 goto :FAIL

echo [8/12] Verifying v3.3 codec auto-gain adapter...
".venv\Scripts\python.exe" .\scripts\verify_v33_app.py
if errorlevel 1 goto :FAIL

echo [9/12] Verifying v3.4 smart delay adapter...
".venv\Scripts\python.exe" .\scripts\verify_v34_app.py
if errorlevel 1 goto :FAIL

echo [10/12] Verifying v3.5 adaptive tail adapter...
".venv\Scripts\python.exe" .\scripts\verify_v35_app.py
if errorlevel 1 goto :FAIL

echo [11/12] Verifying v3.6 final report synchronization...
".venv\Scripts\python.exe" .\scripts\verify_v36_app.py
if errorlevel 1 goto :FAIL

echo [12/12] Verifying v3.6.1 final metrics and Tail INFO guard...
".venv\Scripts\python.exe" .\scripts\verify_v361_app.py
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo INSTALL COMPLETE

echo HARU Mastering v3.6.1 FINAL METRICS SYNC engine is ready.
echo Use RUN.bat, choose folder + genre + QUALITY+, then start.
echo Use only WAV files inside 01_RELEASE_READY after completion.
echo Optional AI repair tools are NOT required for normal mastering.
echo Run INSTALL_AI_TOOLS.bat only when you want DeepFilterNet / Stem tools.
echo ============================================================
echo.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo INSTALL FAILED

echo Take a screenshot of this window and send it to ChatGPT.
echo ============================================================
echo.
pause
exit /b 1
