@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo This removes only the local .venv setup folder.
echo Your music files and MASTER results will NOT be deleted.
echo.
set /p ANSWER=Type YES to continue: 
if /I not "%ANSWER%"=="YES" exit /b 0

if exist ".venv" rmdir /s /q ".venv"

echo.
echo Reset complete.
echo Run START_HERE.bat to install again.
pause
