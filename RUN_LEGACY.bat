@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo RUN_LEGACY.bat is now a compatibility launcher.
echo Starting the latest HARU Mastering from root RUN.bat...
call "%~dp0RUN.bat"
exit /b %errorlevel%
