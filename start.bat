@echo off
setlocal
cd /d "%~dp0"

echo =================================================================
echo [Local ASR] Starting Local ASR in Console / Debug mode...
echo =================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment (.venv) not found!
    echo.
    echo Please run 'setup_windows.bat' first to install the system.
    echo.
    pause
    exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"
set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%~dp0"

"%PYTHON%" main.py --service all

echo.
echo [Local ASR] Process stopped.
pause
