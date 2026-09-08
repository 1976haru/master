@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"

title HARU MASTERING - OPTIONAL AI TOOLS

echo ============================================================
echo HARU MASTERING v3 - OPTIONAL AI AUDIO TOOLS
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Base environment is missing.
    echo Run INSTALL.bat first.
    pause
    exit /b 1
)

set "PY=.venv\Scripts\python.exe"

echo [1/4] Installing conservative spectral noise repair...
"%PY%" -m pip install --upgrade noisereduce
if errorlevel 1 echo [WARN] noisereduce install failed. Base mastering still works.
echo.

echo [2/4] Installing CPU PyTorch runtime for optional AI repair...
"%PY%" -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 (
    echo [WARN] PyTorch install failed. DeepFilterNet/audio-separator may be unavailable.
) else (
    echo PyTorch ready.
)
echo.

echo [3/4] Installing DeepFilterNet ^(MIT/Apache-2.0^) ...
"%PY%" -m pip install --upgrade deepfilternet
if errorlevel 1 echo [WARN] DeepFilterNet install failed. Other features still work.
echo.

echo [4/4] Installing python-audio-separator CPU edition ^(MIT^) ...
"%PY%" -m pip install --upgrade "audio-separator[cpu]"
if errorlevel 1 echo [WARN] audio-separator install failed. Other features still work.
echo.

echo ============================================================
echo OPTIONAL INSTALL FINISHED
echo ============================================================
echo Notes:
echo - Base mastering does NOT depend on these AI packages.
echo - DeepFilterNet processing is local after installation.
echo - audio-separator may download its selected model on first use.
echo   After the model is cached, separation can run locally/offline.
echo.
"%PY%" .\scripts\verify_v3_features.py
pause
exit /b 0
