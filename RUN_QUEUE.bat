@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    call "%~dp0INSTALL.bat"
)

if exist "%~dp0Suno15_Mastering_v3_10.pyw" (
    echo Starting HARU Mastering v3.10...
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Suno15_Mastering_v3_10.pyw"
) else (
    echo Queue UI not found: Suno15_Mastering_v3_10.pyw
    exit /b 1
)
