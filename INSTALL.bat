@echo off
setlocal EnableExtensions
cd /d "%~dp0"

chcp 65001 >nul
set "PYTHONUTF8=1"

title HARU SUNO 15SET MASTERING - INSTALL

echo ============================================================
echo HARU / SUNO 15SET MASTERING v3.7.2 - GUARANTEED CSV SYNC INSTALL
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
        echo Install Python 3.12 from:
        echo https://www.python.org/downloads/windows/
        echo Enable "Add python.exe to PATH" during setup.
        pause
        exit /b 1
    )
    echo Installing Python 3.12 with winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo Close this window and run START_HERE.bat again.
    pause
    exit /b 0
)

echo Python found: %PY_CMD%
echo.

if exist ".venv\Scripts\python.exe" (
    echo Existing virtual environment found.
) else (
    echo [1/15] Creating virtual environment...
    %PY_CMD% -m venv ".venv"
    if errorlevel 1 goto :FAIL
)

echo [2/15] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :FAIL

echo [3/15] Installing FFmpeg helper and audio analysis libraries...
".venv\Scripts\python.exe" -m pip install --upgrade imageio-ffmpeg numpy scipy soundfile pyloudnorm
if errorlevel 1 goto :FAIL

echo [4/15] Installing HARU Mastering v3.7.2 core from this folder...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :FAIL

echo [5/15] Verifying v3 feature core...
".venv\Scripts\python.exe" .\scripts\verify_v3_features.py
if errorlevel 1 goto :FAIL

echo [6/15] Verifying v3 runtime adapter...
".venv\Scripts\python.exe" .\scripts\verify_v3_app.py
if errorlevel 1 goto :FAIL

echo [7/15] Verifying v3.2 auto-finish adapter...
".venv\Scripts\python.exe" .\scripts\verify_v31_app.py
if errorlevel 1 goto :FAIL

echo [8/15] Verifying v3.3 codec auto-gain adapter...
".venv\Scripts\python.exe" .\scripts\verify_v33_app.py
if errorlevel 1 goto :FAIL

echo [9/15] Verifying v3.4 smart delay adapter...
".venv\Scripts\python.exe" .\scripts\verify_v34_app.py
if errorlevel 1 goto :FAIL

echo [10/15] Verifying v3.5 adaptive tail adapter...
".venv\Scripts\python.exe" .\scripts\verify_v35_app.py
if errorlevel 1 goto :FAIL

echo [11/15] Verifying v3.6 final report synchronization...
".venv\Scripts\python.exe" .\scripts\verify_v36_app.py
if errorlevel 1 goto :FAIL

echo [12/15] Verifying v3.6.1 final metrics and Tail INFO guard...
".venv\Scripts\python.exe" .\scripts\verify_v361_app.py
if errorlevel 1 goto :FAIL

echo [13/15] Verifying v3.7 expanded genre profiles...
".venv\Scripts\python.exe" .\scripts\verify_v37_app.py
if errorlevel 1 goto :FAIL

echo [14/15] Verifying v3.7.1 loudness-safe codec strategy...
".venv\Scripts\python.exe" .\scripts\verify_v371_app.py
if errorlevel 1 goto :FAIL

echo [15/15] Verifying v3.7.2 guaranteed CSV synchronization...
".venv\Scripts\python.exe" .\scripts\verify_v372_app.py
if errorlevel 1 goto :FAIL

echo.
echo ============================================================
echo INSTALL COMPLETE

echo HARU Mastering v3.7.2 GUARANTEED CSV SYNC engine is ready.
echo Codec safety uses lower-ceiling rerenders to preserve loudness.
echo Final LUFS, dBTP and LRA are synchronized from the actual MASTER WAV.
echo v3.7.2 CSV columns are guaranteed in both root and 03_REPORT copies.
echo OLD POP, Korean/Japanese Senior, Showa, Enka, K-POP, Kids Pop and more are available.
echo Use RUN.bat or START_HERE.bat. Do not open Suno15_Mastering.pyw directly.
echo Use only WAV files inside 01_RELEASE_READY after completion.
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
