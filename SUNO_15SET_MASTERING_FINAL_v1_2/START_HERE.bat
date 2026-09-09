@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    call "%~dp0RUN.bat"
    exit /b %errorlevel%
)

call "%~dp0INSTALL.bat"

if exist ".venv\Scripts\pythonw.exe" (
    call "%~dp0RUN.bat"
)

exit /b %errorlevel%
