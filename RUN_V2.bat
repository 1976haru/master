@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Setup is missing. Run INSTALL.bat first.
    pause
    exit /b 1
)

if not exist "%~dp0Suno15_Mastering_v2.pyw" (
    echo v2 adapter not found.
    pause
    exit /b 1
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Suno15_Mastering_v2.pyw"
exit /b 0
