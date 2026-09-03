@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =================================================================
echo        Local ASR - Windows Automated Setup (GPU / CPU-Only)
echo =================================================================
echo.

:: 1. Check Python installation
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3.10+ is not found in PATH!
    echo Please install Python from https://www.python.org/downloads/
    echo Remember to check "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

:: 2. Create Virtual Environment
if not exist ".venv" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [*] Virtual environment .venv already exists.
)

set "VENV_PIP=.venv\Scripts\pip.exe"
set "VENV_PYTHON=.venv\Scripts\python.exe"

echo [*] Upgrading pip...
"%VENV_PIP%" install --upgrade pip

:: 3. Hardware Auto-Detection (GPU vs CPU-Only)
echo.
echo [*] Checking for NVIDIA GPU...
where nvidia-smi >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] NVIDIA GPU detected!
    echo [*] Installing PyTorch with CUDA 12.1 support...
    "%VENV_PIP%" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
) else (
    echo [!] No NVIDIA GPU detected. Switching to CPU-Only mode.
    echo [*] Installing lightweight PyTorch for CPU (~200MB)...
    "%VENV_PIP%" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
)

:: 4. Install Dependencies
echo.
echo [*] Installing project dependencies from requirements.txt...
"%VENV_PIP%" install -r requirements.txt

:: 5. Setup Windows Autostart (Startup Folder)
echo.
set /p AUTOSTART="[*] Do you want Local ASR to start automatically when Windows boots? (Y/N, default Y): "
if "%AUTOSTART%"=="" set AUTOSTART=Y
if /i "%AUTOSTART%"=="Y" (
    echo [*] Creating startup shortcut in Windows Startup folder...
    set "TARGET=%~dp0start.vbs"
    set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LocalASR.lnk"
    powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Local ASR Voice Typing Daemon'; $s.Save()"
    echo [OK] Autostart shortcut created at:
    echo      !SHORTCUT!
)

echo.
echo =================================================================
echo [SUCCESS] Setup completed successfully!
echo.
echo - To run silently in background: Double-click 'start.vbs'
echo - To run with debug console:    Double-click 'start.bat'
echo =================================================================
echo.
pause
