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

if exist "%~dp0Suno15_Mastering_v3.pyw" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Suno15_Mastering_v3.pyw"
) else if exist "%~dp0Suno15_Mastering_v2.pyw" (
    echo v3 adapter not found. Starting v2 application.
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Suno15_Mastering_v2.pyw"
) else (
    echo v2/v3 adapter not found. Starting legacy application.
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0Suno15_Mastering.pyw"
)

exit /b 0
