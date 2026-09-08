@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo First-time setup is required.
    call "%~dp0INSTALL.bat"
)

if not exist ".venv\Scripts\pythonw.exe" (
    echo.
    echo Setup is not complete.
    echo Run START_HERE.bat again after Python installation is complete.
    pause
    exit /b 1
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Suno15_Mastering.pyw"
exit /b 0
