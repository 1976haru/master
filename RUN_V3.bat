@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Virtual environment not found. Run INSTALL.bat first.
    pause
    exit /b 1
)

if not exist "%~dp0Suno15_Mastering_v3.pyw" (
    echo Suno15_Mastering_v3.pyw not found.
    pause
    exit /b 1
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Suno15_Mastering_v3.pyw"
exit /b 0
