@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo This archived legacy launcher now starts the latest root HARU Mastering.
call "%~dp0..\..\RUN.bat"
exit /b %errorlevel%
