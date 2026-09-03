@echo off
setlocal
cd /d "%~dp0"

echo [Local ASR] Starting Local ASR in Console/Debug mode...

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%~dp0"

"%PYTHON%" main.py --service all

pause
