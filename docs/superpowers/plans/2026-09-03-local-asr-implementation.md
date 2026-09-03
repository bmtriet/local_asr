# Local ASR Voice Typing & LoRA Fine-Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete offline Speech-to-Text system with `Qwen3-ASR-0.6B`, a global hotkey voice typing daemon with animated tray icon and auto-typing into focused windows, SQLite storage for audio & corrections, LoRA continual fine-tuning pipeline, and a modern dark-mode Web UI.

**Architecture:** 
- ASR engine wraps `Qwen3-ASR-0.6B` with dynamic PEFT LoRA loading.
- System tray daemon captures audio via PyAudio/SoundDevice on hotkey (`Ctrl+Alt+Space`), queries ASR engine, updates tray icon state, and simulates Unicode typing via X11 clipboard/`xdotool`.
- FastAPI backend serves SQLite history, audio streaming, manual correction API, LoRA training triggers, and public REST inference endpoints.
- Web UI provides an audio playback interface, inline word correction, and a real-time LoRA training monitor.

**Tech Stack:** Python 3.10+, PyTorch (CUDA 12.8), Transformers, PEFT, FastAPI, Uvicorn, SQLite3, PyStray, Pillow, Pynput, xdotool, HTML5/CSS3/Vanilla JS.

**Spec:** `docs/superpowers/specs/2026-09-03-local-asr-design.md`

## Global Constraints
- Python 3.10 environment in virtual environment `.venv`.
- Model: `Qwen/Qwen3-ASR-0.6B` running on GPU (RTX 5060 Ti).
- Desktop: Linux X11 with `xdotool` for text injection.
- UI: Vanilla HTML5/CSS/JavaScript with responsive dark mode aesthetics.

---

### Task 1: Environment & Dependency Setup

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.get_settings()` returning system configuration (hotkey, model_path, db_path, server port, etc.).

- [ ] **Step 1: Write the failing test for configuration**

```python
# tests/test_config.py
from config import get_settings

def test_default_settings():
    settings = get_settings()
    assert settings.HOTKEY == "ctrl+alt+space"
    assert settings.MODEL_NAME == "Qwen/Qwen3-ASR-0.6B"
    assert settings.DB_PATH.endswith("local_asr.db")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Create virtual environment and install dependencies**

Create `requirements.txt` with `fastapi`, `uvicorn`, `torch`, `transformers`, `peft`, `pystray`, `pillow`, `pynput`, `sounddevice`, `numpy`, `scipy`, `pytest`.
Setup virtual environment in `.venv`.

- [ ] **Step 4: Implement `config.py`**

Create `config.py` with dataclass/Pydantic `Settings` and default paths.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt config.py tests/test_config.py
git commit -m "chore: setup dependencies and configuration module"
```

---

### Task 2: Database Layer & Audio File Management

**Files:**
- Create: `storage/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: `config.Settings`
- Produces: 
  - `Database.init_db()`
  - `Database.save_transcription(audio_path, duration, raw_text) -> int`
  - `Database.get_transcriptions(limit=50, offset=0) -> List[dict]`
  - `Database.update_correction(item_id, corrected_text) -> bool`
  - `Database.get_samples_for_training() -> List[dict]`
  - `Database.mark_samples_trained(ids: List[int]) -> bool`

- [ ] **Step 1: Write the failing test for database operations**

```python
# tests/test_database.py
import os
import pytest
from storage.database import Database

@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test.db")
    database = Database(db_path=db_file)
    database.init_db()
    return database

def test_transcription_lifecycle(db):
    row_id = db.save_transcription("audio/test.wav", 2.5, "xin chào thế giới")
    assert row_id > 0
    
    items = db.get_transcriptions()
    assert len(items) == 1
    assert items[0]["raw_text"] == "xin chào thế giới"
    assert items[0]["corrected_text"] == "xin chào thế giới"
    assert items[0]["is_reviewed"] == 0

    success = db.update_correction(row_id, "Xin chào Thế Giới")
    assert success is True
    
    items = db.get_transcriptions()
    assert items[0]["corrected_text"] == "Xin chào Thế Giới"
    assert items[0]["is_reviewed"] == 1

    training_samples = db.get_samples_for_training()
    assert len(training_samples) == 1
    assert training_samples[0]["id"] == row_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_database.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `storage/database.py`**

Implement SQLite initialization, connection context manager, and CRUD functions with parameterized queries.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add storage/database.py tests/test_database.py
git commit -m "feat: implement SQLite database storage layer"
```

---

### Task 3: ASR Inference Engine Wrapper & LoRA Loader

**Files:**
- Create: `asr_engine/engine.py`
- Test: `tests/test_asr_engine.py`

**Interfaces:**
- Consumes: `config.Settings`, audio file/numpy array
- Produces:
  - `ASREngine.load_model()`
  - `ASREngine.transcribe(audio_source: str | np.ndarray) -> str`
  - `ASREngine.load_lora_adapter(adapter_dir: str)`
  - `ASREngine.unload_lora_adapter()`

- [ ] **Step 1: Write test for ASR engine interface with mock and real pipeline check**

```python
# tests/test_asr_engine.py
import pytest
from unittest.mock import MagicMock
from asr_engine.engine import ASREngine

def test_asr_engine_mock_transcribe():
    engine = ASREngine(model_name="dummy", device="cpu", lazy_load=True)
    engine._mock_transcribe = MagicMock(return_value="xin chào")
    assert engine._mock_transcribe("dummy.wav") == "xin chào"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_asr_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `asr_engine/engine.py`**

Implement `ASREngine` supporting:
- Loading model via Hugging Face (`AutoModelForSpeechSeq2Seq` or official Qwen ASR pipeline) with CUDA/fp16/bf16.
- Dynamic LoRA adapter attaching/detaching via `PeftModel`.
- Preprocessing audio to 16kHz mono.
- Fallback/mock mode for lightweight automated testing without loading full 0.6B weights during unit tests.

- [ ] **Step 4: Run unit tests**

Run: `.venv/bin/pytest tests/test_asr_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add asr_engine/engine.py tests/test_asr_engine.py
git commit -m "feat: implement ASR inference engine wrapper with PEFT LoRA support"
```

---

### Task 4: Voice Typing Daemon, Hotkey, Animated Tray Icon & Text Injection

**Files:**
- Create: `daemon/audio_recorder.py`
- Create: `daemon/injector.py`
- Create: `daemon/tray.py`
- Create: `daemon/service.py`
- Test: `tests/test_injector.py`
- Test: `tests/test_audio_recorder.py`

**Interfaces:**
- Consumes: `ASREngine`, `Database`, `config.Settings`
- Produces:
  - `AudioRecorder.start_recording()`, `AudioRecorder.stop_recording() -> str`
  - `TextInjector.inject_text(text: str)`
  - `TrayIndicator.set_state(state: str)` (idle, recording, transcribing)
  - `VoiceTypingService.start()`

- [ ] **Step 1: Write unit tests for TextInjector and AudioRecorder**

```python
# tests/test_injector.py
from daemon.injector import TextInjector
from unittest.mock import patch

def test_injector_formats():
    injector = TextInjector()
    with patch("subprocess.run") as mock_run:
        injector.inject_text("thử nghiệm tiếng Việt")
        assert mock_run.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_injector.py -v`
Expected: FAIL

- [ ] **Step 3: Implement TextInjector & AudioRecorder**

- `TextInjector`: Uses clipboard copy + `xdotool key --clearmodifiers ctrl+v` or `xdotool type` for proper UTF-8 Vietnamese diacritics.
- `AudioRecorder`: Uses `sounddevice` / PyAudio to stream chunks into WAV format.
- `TrayIndicator`: Uses `pystray` + `Pillow` to dynamically render icons (green mic for idle, animated red pulsing circle for recording, yellow spinner for processing).
- `VoiceTypingService`: Binds global hotkey (`Ctrl+Alt+Space`), manages state machine (Idle -> Recording -> Transcribing -> Injecting -> Saving to DB).

- [ ] **Step 4: Run unit tests**

Run: `.venv/bin/pytest tests/test_injector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add daemon/ tests/test_injector.py
git commit -m "feat: implement voice typing daemon, hotkey listener and tray indicator"
```

---

### Task 5: LoRA Continual Fine-Tuning Pipeline

**Files:**
- Create: `training/dataset_builder.py`
- Create: `training/lora_trainer.py`
- Test: `tests/test_training_pipeline.py`

**Interfaces:**
- Consumes: `Database`, `ASREngine`
- Produces:
  - `DatasetBuilder.prepare_hf_dataset() -> Dataset`
  - `LoRATrainer.start_training(epochs, lr, batch_size, status_callback) -> str (adapter_dir)`
  - `LoRATrainer.get_status() -> dict`

- [ ] **Step 1: Write unit test for training pipeline dataset preparation**

```python
# tests/test_training_pipeline.py
from training.dataset_builder import DatasetBuilder
from unittest.mock import MagicMock

def test_dataset_builder():
    db_mock = MagicMock()
    db_mock.get_samples_for_training.return_value = [
        {"audio_path": "a.wav", "corrected_text": "câu một"},
        {"audio_path": "b.wav", "corrected_text": "câu hai"}
    ]
    builder = DatasetBuilder(db_mock)
    samples = builder.collect_samples()
    assert len(samples) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_training_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `training/dataset_builder.py` and `training/lora_trainer.py`**

- Use `peft.LoraConfig` (`r=8, lora_alpha=32, target_modules=["q_proj", "v_proj"]`).
- Non-blocking asynchronous training worker running in separate process/thread.
- Metric callback reporting epoch, step, and current training loss.
- Auto-save to `data/adapters/lora_latest/` and trigger `asr_engine.load_lora_adapter()`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_training_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add training/ tests/test_training_pipeline.py
git commit -m "feat: implement LoRA fine-tuning pipeline and dataset generator"
```

---

### Task 6: FastAPI Backend API

**Files:**
- Create: `web/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces REST endpoints:
  - `GET /api/history`
  - `POST /api/history/{id}/correct`
  - `GET /api/audio/{id}`
  - `POST /api/v1/transcribe` (Public ASR API)
  - `POST /api/train/start`
  - `GET /api/train/status`
  - `GET /api/settings` & `POST /api/settings`

- [ ] **Step 1: Write test for FastAPI endpoints**

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from web.api import app

client = TestClient(app)

def test_get_history_empty():
    response = client.get("/api/history")
    assert response.status_code == 200
    assert "items" in response.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `web/api.py`**

- Mount endpoints for history retrieval, correction updates, audio streaming (`FileResponse`), training triggers, and settings.
- Implement `/api/v1/transcribe` accepting `multipart/form-data` audio file.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/api.py tests/test_api.py
git commit -m "feat: implement FastAPI REST backend endpoints"
```

---

### Task 7: Modern Dark-Mode Web UI

**Files:**
- Create: `web/static/index.html`
- Create: `web/static/css/style.css`
- Create: `web/static/js/app.js`

**Interfaces:**
- Consumes: `/api/*` endpoints
- Features:
  - History cards with mini audio player.
  - Inline word-level correction editor (highlight mismatched words between `raw_text` and `corrected_text`).
  - LoRA Fine-Tuning Dashboard: Training trigger button, active status, loss progress bar.
  - Settings panel: customize hotkey, toggle sound feedback.

- [ ] **Step 1: Create HTML structure with semantic tags and accessible controls**
- [ ] **Step 2: Implement modern CSS design system (Dark mode, glassmorphism, Inter font, smooth transitions)**
- [ ] **Step 3: Implement JavaScript state & API interaction (Fetch history, audio playback, inline word edit, polling training status)**
- [ ] **Step 4: Commit**

```bash
git add web/static/
git commit -m "feat: create modern dark-mode Web UI for history correction and LoRA training"
```

---

### Task 8: Integration & End-to-End Verification

**Files:**
- Create: `main.py`
- Test: `tests/test_e2e.py`

- [ ] **Step 1: Create `main.py` entrypoint allowing running:**
  - `python main.py --service all` (Runs daemon + web server + ASR engine)
  - `python main.py --service daemon`
  - `python main.py --service web`
- [ ] **Step 2: Run end-to-end integration test**
- [ ] **Step 3: Verify with real microphone recording and hotkey on desktop**
- [ ] **Step 4: Final commit and summary**
