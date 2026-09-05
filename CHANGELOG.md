# Changelog

All notable changes to the **Local ASR & Voice Typing** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.2] - 2026-09-05

### 🚀 Added & Enhanced
- **Profile Rename & Editing Functionality**:
  - Implemented `PUT /api/profiles/{profile_id}` API endpoint and connected to the underlying SQLite database layer.
  - Added an interactive **Edit Profile** modal to the Web UI allowing users to easily modify display names and descriptions for any profile (including the default profile).
  - Added unit test coverage in `tests/test_profiles.py` verifying profile update operations.
- **Documentation Internationalization**:
  - Fully translated `README.md` into English with complete setup guides (Linux, macOS, Windows 1-Click/manual), architecture notes, and configuration references.

### 🐛 Fixed
- **LoRA Adapter Unload on Profile Switching**:
  - Implemented `unload_lora_adapter` in `ASREngine` to safely detach/disable PEFT LoRA adapters when switching to a profile that does not have trained weights, preventing crashes during profile switching.

---

## [0.1.1] - 2026-09-04

### 🚀 Added & Enhanced
- **Qwen2.5-0.5B Loading Toggle & Resource Optimization**:
  - Added a toggle switch in the Web UI to enable or disable loading the `Qwen2.5-0.5B-Instruct` translation & smart grammar model.
  - When toggled off, the model is kept unloaded (or completely freed from GPU VRAM & system RAM via `unload_model()` + `torch.cuda.empty_cache()`), saving ~1.0GB memory and significantly accelerating app startup time for users who only require pure Speech-To-Text.
- **Full-Width Web UI Layout**:
  - Upgraded the Web Studio layout to 100% full screen width, optimizing data grid space and multi-card visual hierarchy on widescreen monitors.
- **User Clipboard Preservation**:
  - Automatically backs up the user's existing clipboard contents prior to text injection and restores it immediately after pasting (supporting Linux X11, macOS, and Windows). The user's copied clipboard data is never overwritten or lost.
- **"About & GitHub" Author & Project Modal**:
  - Added an **"About & GitHub"** menu item on the System Tray to open the official repository: [github.com/bmtriet/local_asr](https://github.com/bmtriet/local_asr).
  - Added an **"About"** header button and popup dialog on the Web Studio interface featuring author **Triet Bui (@bmtriet)**, project architecture summary, and quick links.
- **Enlarged System Tray Icon (~100%)**:
  - Doubled the diameter of the idle green microphone badge for crisp visibility on high-resolution system taskbars while preserving smooth pulsing recording animations.
- **Expanded OSD Background Ellipse**:
  - Expanded radial background ellipse dimensions by 20% (`rx * 1.20`, `ry * 1.20`) giving audio waveforms and status text generous breathing room.

### 🐛 Fixed
- **System Tray "Restart App" Process Crash**:
  - Re-engineered application restart mechanism to launch a clean independent subprocess and gracefully exit, preventing socket lockups or freeze states.

---

## [0.1.0] - 2026-09-04

### 🚀 Added
- **Zero-Latency Audio Recording**: Immediate audio capture upon hotkey activation with zero startup lag, eliminating truncated initial syllables.
- **Vietnamese Inverse Text Normalization (ITN)**: Ultra-fast regex rule-based engine converting spoken numbers (phone numbers, OTPs, currency, dates, times, card digits) into natural numerical digits in < 0.001s.
- **OSD Multi-Language & Real-Time Translation**: Interactive canvas overlay supporting instant translation switching:
  - `[E]`: Translate to English.
  - `[Z]`: Translate to Traditional Chinese.
  - `[Space / Timeout]`: Retain original Vietnamese transcription.
  - `[ESC]`: Cancel recording immediately.
- **Synthetic Audio Feedback Cues**:
  - Gentle sine chimes for Recording Start, Recording Stop, and Cancellation (ESC) generated directly via `sounddevice` + `numpy` without external audio assets.
- **Real-Time Volume & VU Meter on OSD**:
  - Live color-coded volume gauge displaying real-time microphone decibels directly on the OSD canvas to confirm active microphone pickup.
- **Cursor-Aware Multi-Monitor Positioning**:
  - Dynamic multi-monitor detection positioning the OSD overlay on whichever screen currently contains the user's active mouse pointer.
- **Translucent Radial Glass OSD**:
  - 20% opacity reduction across background radial gradient stops for a sleek glassmorphic floating HUD.
- **Push-to-Talk (Hold-to-Talk) Mode**:
  - Toggle between traditional one-click Toggle Mode and Hold-to-Talk (hold shortcut to speak, release to type).
- **Silence VAD (Voice Activity Detection)**:
  - Automatic silence detection stopping audio recording and triggering transcription seamlessly when speech ceases.
- **Continual LoRA Fine-Tuning**: On-device personalized acoustic adaptation using PyTorch PEFT LoRA with live adapter swapping.
- **Hotword Context Biasing & Multi-Profile Management**: Dedicated domain-specific vocabulary profiles with seamless import/export.
- **Web Changelog Viewer**: Clean, responsive release timeline accessible via `/changelog.html`.
