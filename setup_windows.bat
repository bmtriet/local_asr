@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "LOG_FILE=%~dp0setup_windows.log"
echo ================================================================= > "%LOG_FILE%"
echo Local ASR Windows Setup Log - %DATE% %TIME% >> "%LOG_FILE%"
echo ================================================================= >> "%LOG_FILE%"

echo =================================================================
echo        Local ASR - Windows Automated Setup (GPU / CPU-Only)
echo =================================================================
echo.
echo [*] Chi tiet qua trinh cai dat se duoc ghi vao file:
echo     setup_windows.log
echo.

:: -----------------------------------------------------------------
:: 1. Kiem tra Python va phien ban phu hop (3.10 - 3.12, 64-bit)
:: -----------------------------------------------------------------
set "ERR_STEP=Kiem tra phien ban Python tren may"
echo [*] Dang kiem tra Python tren may cua ban...
set "PYTHON_CMD="

:: Kiem tra lenh 'python' co ton tai va chay duoc khong (khong phai shortcut ao cua Microsoft Store)
where python >nul 2>&1
if !ERRORLEVEL! NEQ 0 goto :CHECK_PY_LAUNCHER
python -c "import sys, struct; sys.exit(0 if sys.version_info[0]==3 and sys.version_info[1] in (10,11,12) and struct.calcsize('P')==8 else 1)" >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=python"
    goto :PYTHON_FOUND
)

:CHECK_PY_LAUNCHER
:: Neu 'python' khong hop le, thu kiem tra trinh khoi chay 'py' (Python Launcher san co tren Windows)
where py >nul 2>&1
if !ERRORLEVEL! NEQ 0 goto :PYTHON_NOT_FOUND
py -3.11 -c "import sys, struct; sys.exit(0 if struct.calcsize('P')==8 else 1)" >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=py -3.11"
    goto :PYTHON_FOUND
)
py -3.10 -c "import sys, struct; sys.exit(0 if struct.calcsize('P')==8 else 1)" >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=py -3.10"
    goto :PYTHON_FOUND
)
py -3.12 -c "import sys, struct; sys.exit(0 if struct.calcsize('P')==8 else 1)" >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=py -3.12"
    goto :PYTHON_FOUND
)
py -3 -c "import sys, struct; sys.exit(0 if sys.version_info[0]==3 and sys.version_info[1] in (10,11,12) and struct.calcsize('P')==8 else 1)" >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=py -3"
    goto :PYTHON_FOUND
)

:PYTHON_NOT_FOUND
:: Neu van khong tim thay Python phu hop
if "!PYTHON_CMD!"=="" (
    echo.
    echo =================================================================
    echo [ERROR] KHONG TIM THAY PHIEN BAN PYTHON PHU HOP!
    echo =================================================================
    echo.
    echo YEU CAU HE THONG:
    echo  - Can cai dat Python 3.10, 3.11 hoac 3.12 (BAN 64-BIT).
    echo  - KHUYEN NGHI CAI DAT TOT NHAT: Python 3.11.9 (64-bit)
    echo    Link tai truc tiep:
    echo    https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    echo -----------------------------------------------------------------
    echo LUU Y CUCT KY QUAN TRONG KHI CAI PYTHON:
    echo  1. O man hinh dau tien cua bo cai dat, BAT BUOC TICK CHON vao o:
    echo     [x] "Add python.exe to PATH"
    echo.
    echo  2. Neu Windows tu dong bat Microsoft Store khi go lenh python:
    echo     Vao: Windows Settings -^> Apps -^> Advanced app settings -^> App execution aliases
    echo     Chuyen 2 muc sau sang TAT (OFF):
    echo       - App Installer (python.exe)
    echo       - App Installer (python3.exe)
    echo =================================================================
    echo.
    echo Chi tiet da duoc ghi vao file: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

echo [OK] Phat hien Python phu hop: !PYTHON_CMD!
!PYTHON_CMD! -c "import sys, struct; arch = str(struct.calcsize('P') * 8) + '-bit'; print(f'[*] Phien ban: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({arch})')"
!PYTHON_CMD! -c "import sys, struct; arch = str(struct.calcsize('P') * 8) + '-bit'; print(f'[*] Phien ban: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} ({arch})')" >> "%LOG_FILE%" 2>&1

:: -----------------------------------------------------------------
:: 2. Tao moi truong ao (.venv)
:: -----------------------------------------------------------------
set "ERR_STEP=Khoi tao moi truong ao (.venv)"
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [*] Dang tao moi truong ao .venv (Co the mat vai giay)...
    !PYTHON_CMD! -m venv .venv >> "%LOG_FILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Khong the tao thu muc .venv!
        goto :ON_ERROR
    )
    echo [OK] Da tao thanh cong moi truong ao .venv.
) else (
    echo [*] Thu muc moi truong ao .venv da ton tai san.
)

set "VENV_PIP=.venv\Scripts\pip.exe"
set "VENV_PYTHON=.venv\Scripts\python.exe"

if not exist "!VENV_PIP!" (
    echo [ERROR] Khong tim thay tap tin .venv\Scripts\pip.exe!
    set "ERR_STEP=Kiem tra tep tin pip trong .venv"
    goto :ON_ERROR
)

set "ERR_STEP=Nang cap pip trong moi truong ao"
echo.
echo [*] Dang kiem tra va nang cap pip...
"!VENV_PIP!" install --upgrade pip >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [CANH BAO] Khong the nang cap pip, tiep tuc su dung phien ban hien tai...
)

:: -----------------------------------------------------------------
:: 3. Tu dong nhan dien Card do hoa (NVIDIA GPU vs CPU-Only)
:: -----------------------------------------------------------------
set "ERR_STEP=Cai dat PyTorch phu hop voi phan cung"
echo.
echo [*] Dang kiem tra phan cung do hoa (GPU / CPU)...
where nvidia-smi >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo [OK] Tim thay Card do hoa NVIDIA GPU!
    echo [*] Dang cai dat PyTorch voi ho tro tang toc CUDA 12.1...
    echo     (Vui long cho vai phut, dung luong goi CUDA khoang 2.5GB)...
    "!VENV_PIP!" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 >> "%LOG_FILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo [CANH BAO] Cai dat ban CUDA gap loi. Tu dong chuyen sang ban CPU nhe...
        "!VENV_PIP!" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu >> "%LOG_FILE%" 2>&1
        if !ERRORLEVEL! NEQ 0 goto :ON_ERROR
    )
) else (
    echo [!] Khong phat hien GPU NVIDIA. Tu dong chuyen sang che do CPU-Only.
    echo [*] Dang cai dat ban PyTorch sieu nhe danh cho CPU (~200MB)...
    "!VENV_PIP!" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu >> "%LOG_FILE%" 2>&1
    if !ERRORLEVEL! NEQ 0 goto :ON_ERROR
)

:: -----------------------------------------------------------------
:: 4. Cai dat cac goi thu vien con lai tu requirements.txt
:: -----------------------------------------------------------------
set "ERR_STEP=Cai dat cac thu vien du an tu requirements.txt"
echo.
echo [*] Dang cai dat cac goi thu vien phu thuoc (FastAPI, Transformers, PEFT, SoundDevice,...)...
"!VENV_PIP!" install -r requirements.txt >> "%LOG_FILE%" 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Cai dat thu vien tu requirements.txt that bai!
    goto :ON_ERROR
)

:: -----------------------------------------------------------------
:: 5. Tuy chon: Cai dat Mo hinh Dich thuat & Ngu phap Qwen2.5 (0.5B)
:: -----------------------------------------------------------------
echo.
echo =================================================================
echo [*] CAU HINH TINH NANG DICH THUAT & SUA NGU PHAP (QWEN2.5-0.5B):
echo  - Neu CHON (Y): He thong se tai mo hinh Qwen2.5-0.5B (~1.0GB)
echo    de ho tro dich sang Tieng Anh [E], Tieng Trung [Z] va sua loi.
echo  - Neu KHONG (N): Che do STT Thuan Tuy (Tiet kiem ~1.0GB dung luong,
echo    chi nhan dien giong noi Tieng Viet, toi uu may yeu/RAM it).
echo =================================================================
set /p INSTALL_TRANSLATE="[*] Ban co muon tai them mo hinh Dich thuat Qwen2.5 khong? (Y/N, mac dinh N): "
if "!INSTALL_TRANSLATE!"=="" set INSTALL_TRANSLATE=N
if /i "!INSTALL_TRANSLATE!"=="Y" (
    echo.
    echo [*] Dang tai va khoi tao bo nho dem cho Qwen2.5-0.5B-Instruct (~1.0GB)...
    "!VENV_PYTHON!" -c "from transformers import AutoModelForCausalLM, AutoTokenizer; m='Qwen/Qwen2.5-0.5B-Instruct'; AutoTokenizer.from_pretrained(m); AutoModelForCausalLM.from_pretrained(m)" >> "%LOG_FILE%" 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Da tai va luu tru thanh cong mo hinh dich thuat Qwen2.5!
    ) else (
        echo [CANH BAO] Khong the tai truoc Qwen2.5, se duoc tai tu dong khi kich hoat dich.
    )
) else (
    echo.
    echo [OK] Ban da chon che do STT Thuan Tuy (Pure STT Mode).
    echo      Bo qua tai Qwen2.5, tiet kiem ~1.0GB dung luong o cung va RAM!
)

:: -----------------------------------------------------------------
:: 6. Thiet lap tu dong khoi dong cung Windows (Startup folder)
:: -----------------------------------------------------------------
set "ERR_STEP=Tao loi tat khoi dong cung Windows"
echo.
set /p AUTOSTART="[*] Ban co muon Local ASR tu dong chay khi bat may tinh Windows? (Y/N, mac dinh Y): "
if "!AUTOSTART!"=="" set AUTOSTART=Y
if /i "!AUTOSTART!"=="Y" (
    echo [*] Dang tao shortcut trong thu muc Startup...
    set "TARGET=%~dp0start.vbs"
    set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LocalASR.lnk"
    powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Local ASR Voice Typing Daemon'; $s.Save()" >> "%LOG_FILE%" 2>&1
    echo [OK] Da tao loi tat tu khoi dong tai:
    echo      !SHORTCUT!
)

:: -----------------------------------------------------------------
:: 7. Hoan tat cai dat
:: -----------------------------------------------------------------
echo.
echo =================================================================
echo [THANH CONG] Qua trinh cai dat tren Windows da hoan tat 100%!
echo.
echo  - De chay ngam (khong hien cua so):   Nhay dup vao 'start.vbs'
echo  - De chay che do xem log (Debug):     Nhay dup vao 'start.bat'
echo.
echo Toan bo log cai dat da duoc luu tai:
echo %LOG_FILE%
echo =================================================================
echo.
pause
exit /b 0

:: -----------------------------------------------------------------
:: Xu ly khi gap loi (Khong bao gio tu dong tat man hinh)
:: -----------------------------------------------------------------
:ON_ERROR
echo.
echo =================================================================
echo [LOI] QUA TRINH CAI DAT BI DUNG LAI!
echo =================================================================
echo  - Buoc xay ra loi: !ERR_STEP!
echo  - Ma loi tra ve (Exit code): !ERRORLEVEL!
echo.
echo Vui long mo tep nhat ky chi tiet sau de xem nguyen nhan cu the:
echo %LOG_FILE%
echo.
echo Neu can ho tro, ban co the gui noi dung file %LOG_FILE% nay.
echo =================================================================
echo.
pause
exit /b 1
