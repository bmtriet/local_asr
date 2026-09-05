# Local ASR & Voice Typing Daemon (Cross-Platform)

High-performance, 100% offline local speech recognition and voice typing system (**Local ASR Voice Typing**) that operates without requiring internet access. Integrated with the state-of-the-art **Qwen3-ASR (0.6B)** acoustic model, **Qwen2.5 (0.5B)** grammar correction & translation LLM, ultrafast **Vietnamese ITN** (Inverse Text Normalization) module, **Continual LoRA Fine-Tuning**, and **Hotword Context Biasing**.

Seamless cross-platform support across **Linux**, **macOS**, and **Windows** (automatically optimized for **NVIDIA GPU CUDA**, **Apple Silicon MPS**, and **CPU-Only** execution).

---

## 🌟 Key Highlights & Features

- 🎙️ **Zero-Latency Recording**: Instant capture upon hotkey press—never miss initial syllables or sentence beginnings.
- 🚀 **Ultrafast Vietnamese ITN**: Automatically parses spoken number sequences (phone numbers, OTP tokens, card numbers, time, currency, percentages) to natural digits in ~0.001s:
  - *"Không chín tám bảy ba một một tám sáu một"* $\rightarrow$ **`0987311861`**
  - *"Mã thẻ một chín hai một"* $\rightarrow$ **`Mã thẻ 1921`**
  - *"Mười sáu giờ ba mươi phút"* $\rightarrow$ **`16:30`**
- 🌐 **Interactive OSD Language Selector & Translation**:
  - `[E]`: 🇬🇧 Translate directly into English.
  - `[Z]`: 🇨🇳 Translate directly into Traditional Chinese.
  - `[Spacebar / After 2s timeout]`: Automatically auto-dismisses OSD and resumes original speech transcription mode.
  - `[ESC]`: ❌ Instantly cancel at either mode selection or active recording phases.
- 📝 **Bilingual Output (Add Origin Phrase)**: Optional dual-line output including both source transcription and target translation for instant verification.
- 🧠 **Hotword Context Biasing & Memory**: Automatically extracts reviewed terminology, proper nouns, and corrections directly into model prompt context for accurate recognition on future passes.
- 🎯 **Real PyTorch LoRA Fine-Tuning**: Run parameter-efficient fine-tuning directly on corrected audio samples; dynamically loads newly trained weights (`adapter_model.safetensors`) onto GPU within the active runtime.
- 👤 **Multi-Profile Management**: Dedicated user profiles with isolated audio history, custom vocabulary (`vocabulary.json`), and separate LoRA adapter weights. Supports creating, editing profile name/description, switching, and exporting bundles.
- 🔊 **Audio Feedback Cues**: Gentle synthesized chimes on record start, completion, and cancel (ESC).
- 📊 **Real-time Audio VU Meter on OSD**: Visual microphone amplitude monitor displayed right on screen.
- ⚡ **Push-to-Talk & Silence VAD**: Toggle hotkey or hold-to-talk modes with automatic silence detection cut-off.
- 🔄 **System Tray Indicator**: Dynamic tray status indicator (Idle, Recording, Transcribing), providing quick access to Web UI, Restart, and Exit.
- 📜 **Detailed Release Notes**: See [`CHANGELOG.md`](CHANGELOG.md) or the web dashboard at `/changelog.html`.

---

## 🐧 1. Installation & Setup on Linux (Ubuntu / Debian / Fedora / Arch)

### Step 1: Install System Dependencies
Open Terminal and install required system packages for audio, clipboard, and system tray:

```bash
# Ubuntu / Debian:
sudo apt update
sudo apt install -y python3-venv python3-pip portaudio19-dev xclip xdotool libgtk-3-dev libayatana-appindicator3-dev

# Fedora:
sudo dnf install -y portaudio-devel xclip xdotool gtk3-devel libappindicator-gtk3-devel

# Arch Linux:
sudo pacman -S portaudio xclip xdotool gtk3 libappindicator-gtk3
```

### Step 2: Create Virtual Environment & Install Python Dependencies
```bash
# Navigate to project directory
cd local_asr

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install PyTorch:
# For NVIDIA GPU (CUDA):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# For CPU-Only (no GPU):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install project dependencies
pip install -r requirements.txt
```

### Step 3: Launch Application
- **Background Daemon (Recommended):**
  ```bash
  ./start.sh
  ```
  *(Runs silently in background with system tray icon; logs stored in `logs/app.log`)*.

- **Foreground Debug Mode (Live Log Output):**
  ```bash
  ./start.sh --foreground
  ```

- **Stop Application:** Right-click Tray Icon and select **Exit**, or run:
  ```bash
  pkill -f "local_asr/main.py"
  ```

---

## 🍎 2. Installation & Setup on macOS (Apple Silicon M1/M2/M3/M4 & Intel)

### Step 1: Install Homebrew & Audio Dependencies
If Homebrew is not installed, install it from [brew.sh](https://brew.sh/). Then install portaudio:

```bash
brew install portaudio
```

### Step 2: Create Virtual Environment & Install Python Packages
```bash
# Navigate to project directory
cd local_asr

# Create virtual environment with Python 3.10+
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install PyTorch (Official build supports native MPS Acceleration for Apple Silicon)
pip install torch torchvision torchaudio

# Install project dependencies
pip install -r requirements.txt
```

### Step 3: Grant System Permissions (Important!)
macOS enforces strict privacy permissions. Grant permissions to capture global shortcuts and record audio:
1. Open **System Settings** $\rightarrow$ **Privacy & Security**.
2. **Microphone**: Enable permission for **Terminal** (or iTerm2 / VSCode).
3. **Accessibility**: Add and grant permission for **Terminal** (or iTerm2) to allow global hotkey detection and synthetic typing.
4. **Input Monitoring**: Grant permission for Terminal if prompted by macOS.

### Step 4: Launch Application
```bash
source .venv/bin/activate
python main.py --service all
```

---

## 🪟 3. Installation & Setup on Windows (Windows 10 / 11, 64-bit)

### Python Version Requirements:
- **Compatible Versions:** Python **3.10**, **3.11**, or **3.12** (**64-bit**).
- **Recommended Release:** [Python 3.11.9 (64-bit)](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe) (Optimal stability and pre-built wheel compatibility for PyTorch & Transformers).
- **Critical Setup Checks:**
  1. During Python installation, **ALWAYS CHECK: `[x] Add python.exe to PATH`**.
  2. If typing `python` in Command Prompt opens the Microsoft Store:
     - Open **Windows Settings** $\rightarrow$ **Apps** $\rightarrow$ **Advanced app settings** $\rightarrow$ **App execution aliases**.
     - Toggle **OFF** both `App Installer (python.exe)` and `App Installer (python3.exe)`.

### Option A: Automatic 1-Click Setup (Recommended)
1. Verify 64-bit Python is installed as described above.
2. Double-click:
   ```text
   setup_windows.bat
   ```
3. The setup script will automatically:
   - Validate compatible Python runtime (`python`, `py -3.11`, `py -3.10`).
   - Log output to `setup_windows.log`. The command prompt window stays open on error for review.
   - Detect NVIDIA GPU: automatically selects PyTorch CUDA or lightweight PyTorch CPU (~200MB instead of ~3GB).
   - Install all Windows-compatible requirements.
   - Offer to configure autostart via Windows Startup folder (`shell:startup`).

### Option B: Manual Setup via CMD / PowerShell
```cmd
cd local_asr
python -m venv .venv
.\.venv\Scripts\activate

:: With NVIDIA GPU:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: Without GPU (CPU-Only):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

:: Install dependencies:
pip install -r requirements.txt
```

### Launch Application on Windows
- **Silent Background Run (No CMD Window):**
  Double-click:
  ```text
  start.vbs
  ```
- **Foreground Debug Mode (Shows CMD window for live logs):**
  Double-click:
  ```text
  start.bat
  ```

---

## 🖥️ 4. Web Dashboard & Studio Guide

Access the web management dashboard at:
👉 **`http://127.0.0.1:8000`**

Key dashboard features:
1. **User Profiles Management**:
   - Manage multiple profiles (e.g. personal, coding, finance).
   - Edit profile display name and description directly.
   - Export profile bundles containing vocabulary and LoRA adapters.
2. **Recognition History & Corrections**:
   - Play back recorded audio snippets.
   - Edit ground truth transcription to teach the system your speech patterns.
   - Click **Save Review** to queue samples for continual fine-tuning.
3. **LoRA Fine-Tuning Studio**:
   - Monitor count of pending training samples (`pending_samples`).
   - Click **Start LoRA Training** to trigger actual PyTorch fine-tuning on GPU/CPU. Weights are hot-reloaded automatically.
4. **Custom Vocabulary & Keyword Mapping**:
   - Define domain terms, acronyms, and phonetic replacement rules.
   - Export and import custom `vocabulary.json` profiles.
5. **Settings & Preferences**:
   - Reconfigure global hotkeys, audio cues, and OSD placement.
   - Toggle AI grammar correction and bilingual dual-line transcription.

---

## ⚙️ 5. Configuration Options (config.py)

Default settings can be configured in [config.py](config.py) or overridden via environment variables prefixed with `LOCAL_ASR_`:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `HOTKEY` | `ctrl+alt+space` | Hotkey trigger (`ctrl+alt+space`, `f9`, `alt+z`, etc.) |
| `MODEL_NAME` | `Qwen/Qwen3-ASR-0.6B` | Core ASR acoustic model identifier |
| `GRAMMAR_MODEL_NAME` | `Qwen/Qwen2.5-0.5B-Instruct` | Grammar correction & translation model identifier |
| `HOST` | `127.0.0.1` | Web UI bind host |
| `PORT` | `8000` | Web UI bind port |
| `CPU_THREADS` | `4` | Maximum CPU thread concurrency when running without GPU |
| `ADD_ORIGIN_PHRASE` | `False` | Output both original phrase and translation |
| `OSD_POSITION` | `top-left` | Screen placement of floating OSD (`top-left`, `top-right`, `center`, etc.) |

---

## 🧪 6. Automated Unit Tests

The project includes an automated test suite verifying cross-platform services, ITN normalizer, LoRA training, database operations, profiles, and web APIs:

```bash
# Activate virtualenv and run pytest:
PYTHONPATH=. pytest
```
*(All test suites pass 100% across supported environments).*
