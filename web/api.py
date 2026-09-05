import os
import json
from pathlib import Path
from typing import Optional, List, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import get_settings
from storage.database import Database
from asr_engine.engine import ASREngine
from asr_engine.vocabulary import VocabularyManager
from training.lora_trainer import LoRATrainer

app = FastAPI(title="Local ASR System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()
db = Database()
db.init_db()
engine = ASREngine(lazy_load=True)
trainer = LoRATrainer(db=db)
vocab_mgr = VocabularyManager()
daemon_instance: Optional[Any] = None

def set_daemon_instance(d):
    global daemon_instance, engine, db, vocab_mgr
    daemon_instance = d
    if hasattr(d, "engine") and d.engine:
        engine = d.engine
    if hasattr(d, "db") and d.db:
        db = d.db
    if hasattr(d, "normalizer") and getattr(d.normalizer, "vocab_mgr", None):
        vocab_mgr = d.normalizer.vocab_mgr

class CorrectionRequest(BaseModel):
    corrected_text: str

class VocabularyItem(BaseModel):
    target: str
    aliases: List[str] = []
    description: Optional[str] = ""

class TestVocabularyRequest(BaseModel):
    text: str

class SettingsUpdateRequest(BaseModel):
    hotkey: Optional[str] = None
    qwen25_enabled: Optional[bool] = None
    grammar_correction_enabled: Optional[bool] = None
    translation_target: Optional[str] = None
    add_origin_phrase: Optional[bool] = None
    osd_position: Optional[str] = None
    osd_duration: Optional[float] = None
    osd_always_on: Optional[bool] = None
    sound_cues_enabled: Optional[bool] = None
    hotkey_mode: Optional[str] = None
    vad_enabled: Optional[bool] = None
    vad_silence_timeout: Optional[float] = None
    streaming_transcription_enabled: Optional[bool] = None

class ProfileCreateRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""

class ProfileSwitchRequest(BaseModel):
    profile_id: str

class ProfileUpdateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

@app.get("/api/profiles")
def get_profiles_list():
    """Retrieve all profiles with active state."""
    profiles = db.get_profiles()
    active = db.get_active_profile()
    return {
        "profiles": profiles,
        "active_profile": active
    }

@app.post("/api/profiles")
def create_profile_endpoint(payload: ProfileCreateRequest):
    """Create a new user profile."""
    clean_id = payload.id.strip().lower()
    if not clean_id:
        raise HTTPException(status_code=400, detail="Profile ID cannot be empty")
    success = db.create_profile(clean_id, payload.name, payload.description or "")
    if not success:
        raise HTTPException(status_code=400, detail="Profile ID already exists or is invalid")
    return {"status": "created", "profile_id": clean_id}

@app.post("/api/profiles/active")
def switch_active_profile_endpoint(payload: ProfileSwitchRequest):
    """Switch the current active profile."""
    clean_id = payload.profile_id.strip().lower()
    success = db.set_active_profile(clean_id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Switch vocabulary and trainer profile
    vocab_mgr.switch_profile(clean_id)
    trainer.switch_profile(clean_id)
    engine.switch_profile_adapter(clean_id)

    # Sync with daemon if running
    if daemon_instance and hasattr(daemon_instance, "switch_profile"):
        daemon_instance.switch_profile(clean_id)

    return {"status": "switched", "active_profile": db.get_active_profile()}

@app.put("/api/profiles/{profile_id}")
def update_profile_endpoint(profile_id: str, payload: ProfileUpdateRequest):
    """Update profile name and description."""
    clean_id = profile_id.strip().lower()
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Profile name cannot be empty")
    
    success = db.update_profile(clean_id, clean_name, payload.description or "")
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"status": "updated", "profile_id": clean_id, "name": clean_name}

@app.delete("/api/profiles/{profile_id}")
def delete_profile_endpoint(profile_id: str):
    """Delete a user profile (except default)."""
    clean_id = profile_id.strip().lower()
    if clean_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default profile")
    
    # If active profile was deleted, switch active to default
    was_active = (db.get_active_profile().get("id") == clean_id)
    success = db.delete_profile(clean_id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if was_active:
        vocab_mgr.switch_profile("default")
        trainer.switch_profile("default")
        engine.switch_profile_adapter("default")
        if daemon_instance and hasattr(daemon_instance, "switch_profile"):
            daemon_instance.switch_profile("default")

    return {"status": "deleted", "profile_id": clean_id}

@app.get("/api/status")
def get_status():
    active_prof = db.get_active_profile()
    return {
        "status": "ok",
        "model": settings.MODEL_NAME,
        "device": engine.device,
        "is_model_loaded": engine.is_loaded,
        "active_lora": engine.active_adapter_name,
        "active_profile": active_prof
    }

@app.get("/api/history")
def get_history(
    page: int = 1,
    limit: int = 10,
    filter_type: str = "all",
    search: str = "",
    profile_id: Optional[str] = None
):
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit
    
    # Default to current active profile if not specified
    if profile_id is None:
        profile_id = db.get_active_profile().get("id", "default")
    elif profile_id == "all":
        profile_id = None

    total = db.get_transcriptions_count(filter_type=filter_type, search=search, profile_id=profile_id)
    items = db.get_transcriptions(limit=limit, offset=offset, filter_type=filter_type, search=search, profile_id=profile_id)
    total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "profile_id": profile_id
    }

@app.delete("/api/history/{item_id}")
def delete_transcription(item_id: int):
    success = db.delete_transcription(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "id": item_id}

@app.post("/api/history/{item_id}/correct")
def correct_transcription(item_id: int, payload: CorrectionRequest):
    success = db.update_correction(item_id, payload.corrected_text)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "id": item_id, "corrected_text": payload.corrected_text}

@app.get("/api/audio/{item_id}")
def stream_audio(item_id: int):
    item = db.get_transcription_by_id(item_id)
    if not item or not os.path.exists(item["audio_path"]):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(item["audio_path"], media_type="audio/wav")

@app.post("/api/v1/transcribe")
async def public_transcribe(file: UploadFile = File(...)):
    """Public endpoint for other applications to send audio and receive transcription."""
    temp_path = settings.RECORDINGS_DIR / f"api_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    try:
        text = engine.transcribe(str(temp_path))
        return {"text": text}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/api/train/status")
def get_train_status():
    status = trainer.get_status()
    active_profile_id = db.get_active_profile().get("id", "default")
    pending_samples = len(db.get_samples_for_training(profile_id=active_profile_id))
    status["pending_samples"] = pending_samples
    status["profile_id"] = active_profile_id
    return status

@app.post("/api/train/start")
def start_train(epochs: int = 3, lr: float = 1e-4):
    def on_complete(adapter_dir):
        try:
            print(f"[API] Training completed! Reloading adapter into engine from {adapter_dir}...")
            engine.load_lora_adapter(adapter_dir)
            if daemon_instance and hasattr(daemon_instance, "engine") and daemon_instance.engine:
                if daemon_instance.engine is not engine:
                    daemon_instance.engine.load_lora_adapter(adapter_dir)
        except Exception as e:
            print("Failed to auto-reload LoRA adapter:", e)

    started = trainer.start_training(epochs=epochs, lr=lr, on_completed=on_complete, asr_engine=engine)
    if not started:
        raise HTTPException(status_code=400, detail=trainer.last_error or "Cannot start training")
    return {"status": "started"}

@app.get("/api/settings")
def get_current_settings():
    saved_hotkey = db.get_setting("hotkey")
    active_hotkey = saved_hotkey or settings.HOTKEY
    qwen25_enabled_str = db.get_setting("qwen25_enabled", str(getattr(settings, "QWEN25_ENABLED", True))).lower()
    qwen25_enabled = (qwen25_enabled_str == "true")
    grammar_enabled_str = db.get_setting("grammar_correction_enabled", str(settings.GRAMMAR_CORRECTION_ENABLED)).lower()
    grammar_enabled = (grammar_enabled_str == "true")
    translation_target = db.get_setting("translation_target", settings.TRANSLATION_TARGET)
    add_origin_phrase_str = db.get_setting("add_origin_phrase", str(settings.ADD_ORIGIN_PHRASE)).lower()
    add_origin_phrase = (add_origin_phrase_str == "true")
    osd_position = db.get_setting("osd_position", settings.OSD_POSITION)
    osd_duration_str = db.get_setting("osd_duration", str(settings.OSD_DURATION))
    try:
        osd_duration = float(osd_duration_str)
    except Exception:
        osd_duration = settings.OSD_DURATION
    osd_always_on_str = db.get_setting("osd_always_on", str(settings.OSD_ALWAYS_ON)).lower()
    osd_always_on = (osd_always_on_str == "true")

    sound_cues_str = db.get_setting("sound_cues_enabled", "true").lower()
    sound_cues_enabled = (sound_cues_str == "true")
    hotkey_mode = db.get_setting("hotkey_mode", "toggle").lower()
    vad_enabled_str = db.get_setting("vad_enabled", "false").lower()
    vad_enabled = (vad_enabled_str == "true")
    vad_timeout_str = db.get_setting("vad_silence_timeout", "2.0")
    try:
        vad_silence_timeout = float(vad_timeout_str)
    except Exception:
        vad_silence_timeout = 2.0

    streaming_transcription_str = db.get_setting("streaming_transcription_enabled", str(settings.STREAMING_TRANSCRIPTION_ENABLED)).lower()
    streaming_transcription_enabled = (streaming_transcription_str == "true")

    return {
        "hotkey": active_hotkey,
        "sample_rate": settings.SAMPLE_RATE,
        "model_name": settings.MODEL_NAME,
        "device": engine.device,
        "qwen25_enabled": qwen25_enabled,
        "grammar_correction_enabled": grammar_enabled,
        "translation_target": translation_target,
        "add_origin_phrase": add_origin_phrase,
        "osd_position": osd_position,
        "osd_duration": osd_duration,
        "osd_always_on": osd_always_on,
        "sound_cues_enabled": sound_cues_enabled,
        "hotkey_mode": hotkey_mode,
        "vad_enabled": vad_enabled,
        "vad_silence_timeout": vad_silence_timeout,
        "streaming_transcription_enabled": streaming_transcription_enabled
    }

@app.post("/api/settings")
def update_settings(payload: SettingsUpdateRequest):
    if payload.hotkey:
        cleaned_hotkey = payload.hotkey.strip().lower()
        settings.HOTKEY = cleaned_hotkey
        db.set_setting("hotkey", cleaned_hotkey)
        if daemon_instance:
            daemon_instance.update_hotkey(cleaned_hotkey)

    if payload.qwen25_enabled is not None:
        settings.QWEN25_ENABLED = payload.qwen25_enabled
        db.set_setting("qwen25_enabled", str(payload.qwen25_enabled).lower())
        if daemon_instance and hasattr(daemon_instance, "set_qwen25_enabled"):
            daemon_instance.set_qwen25_enabled(payload.qwen25_enabled)

    if payload.grammar_correction_enabled is not None:
        settings.GRAMMAR_CORRECTION_ENABLED = payload.grammar_correction_enabled
        db.set_setting("grammar_correction_enabled", str(payload.grammar_correction_enabled).lower())

    if payload.translation_target is not None:
        cleaned_target = payload.translation_target.strip().lower()
        settings.TRANSLATION_TARGET = cleaned_target
        db.set_setting("translation_target", cleaned_target)

    if payload.add_origin_phrase is not None:
        settings.ADD_ORIGIN_PHRASE = payload.add_origin_phrase
        db.set_setting("add_origin_phrase", str(payload.add_origin_phrase).lower())

    if payload.osd_position is not None:
        cleaned_pos = payload.osd_position.strip().lower()
        settings.OSD_POSITION = cleaned_pos
        db.set_setting("osd_position", cleaned_pos)

    if payload.osd_duration is not None:
        settings.OSD_DURATION = max(0.5, float(payload.osd_duration))
        db.set_setting("osd_duration", str(settings.OSD_DURATION))

    if payload.osd_always_on is not None:
        settings.OSD_ALWAYS_ON = payload.osd_always_on
        db.set_setting("osd_always_on", str(payload.osd_always_on).lower())

    if payload.sound_cues_enabled is not None:
        db.set_setting("sound_cues_enabled", str(payload.sound_cues_enabled).lower())

    if payload.hotkey_mode is not None:
        cleaned_mode = payload.hotkey_mode.strip().lower()
        if cleaned_mode in ["toggle", "hold"]:
            db.set_setting("hotkey_mode", cleaned_mode)

    if payload.vad_enabled is not None:
        db.set_setting("vad_enabled", str(payload.vad_enabled).lower())

    if payload.vad_silence_timeout is not None:
        db.set_setting("vad_silence_timeout", str(max(0.5, float(payload.vad_silence_timeout))))

    if payload.streaming_transcription_enabled is not None:
        settings.STREAMING_TRANSCRIPTION_ENABLED = payload.streaming_transcription_enabled
        db.set_setting("streaming_transcription_enabled", str(payload.streaming_transcription_enabled).lower())

    if daemon_instance and hasattr(daemon_instance, "update_ux_settings"):
        daemon_instance.update_ux_settings(
            sound_cues=payload.sound_cues_enabled,
            hotkey_mode=payload.hotkey_mode,
            vad_enabled=payload.vad_enabled,
            vad_timeout=payload.vad_silence_timeout
        )
        
    return {"status": "updated", "settings": get_current_settings()}

@app.get("/api/vocabulary")
def get_vocabulary():
    """Retrieve all vocabulary entries."""
    return {"items": vocab_mgr.get_all()}

@app.post("/api/vocabulary")
def upsert_vocabulary(item: VocabularyItem):
    """Add or update a vocabulary entry."""
    success = vocab_mgr.upsert(item.target, item.aliases, item.description or "")
    if not success:
        raise HTTPException(status_code=400, detail="Invalid target word or failed to save")
    return {"status": "success", "item": item.model_dump()}

@app.delete("/api/vocabulary/{target}")
def delete_vocabulary(target: str):
    """Delete a vocabulary entry by target word."""
    success = vocab_mgr.delete(target)
    if not success:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    return {"status": "success", "target": target}

@app.post("/api/vocabulary/test")
def test_vocabulary_mapping(payload: TestVocabularyRequest):
    """Test mapping an input phrase to its normalized vocabulary form."""
    mapped_text = vocab_mgr.apply(payload.text)
    return {
        "original": payload.text,
        "mapped": mapped_text,
        "changed": payload.text.strip() != mapped_text.strip()
    }

@app.get("/api/vocabulary/export")
def export_vocabulary(profile_id: Optional[str] = None):
    """Export the vocabulary.json file for current or specified profile."""
    if not profile_id:
        profile_id = db.get_active_profile().get("id", "default")
    
    clean_id = profile_id.strip().lower()
    if clean_id == "default":
        vocab_path = settings.VOCABULARY_PATH
    else:
        vocab_path = settings.DATA_DIR / "profiles" / clean_id / "vocabulary.json"

    if not vocab_path.exists():
        vocab_mgr.save()

    return FileResponse(
        str(vocab_path),
        media_type="application/json",
        filename=f"vocabulary_{clean_id}.json"
    )

@app.get("/api/train/export")
def export_lora_adapter(profile_id: Optional[str] = None):
    """Export the trained LoRA adapter weights for specified or active profile as a zip archive."""
    import shutil
    import tempfile

    if not profile_id:
        profile_id = db.get_active_profile().get("id", "default")
    clean_id = profile_id.strip().lower()

    # Look for adapter directory
    adapter_path = settings.ADAPTERS_DIR / clean_id
    if not adapter_path.exists() and clean_id == "default":
        legacy = settings.ADAPTERS_DIR / "lora_latest"
        if legacy.exists():
            adapter_path = legacy

    if not adapter_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No trained LoRA adapter found for profile '{clean_id}'. Please run training first."
        )

    # Check that adapter weights exist
    has_config = (adapter_path / "adapter_config.json").exists()
    has_weights = (adapter_path / "adapter_model.safetensors").exists() or (adapter_path / "adapter_model.bin").exists()
    if not has_config or not has_weights:
        raise HTTPException(
            status_code=404,
            detail=f"LoRA adapter in '{adapter_path.name}' is incomplete or lacks trained weights."
        )

    # Create temporary zip archive
    temp_dir = tempfile.mkdtemp()
    zip_base_name = os.path.join(temp_dir, f"lora_adapter_{clean_id}")
    archive_file = shutil.make_archive(zip_base_name, "zip", str(adapter_path))

    return FileResponse(
        archive_file,
        media_type="application/zip",
        filename=f"lora_adapter_{clean_id}.zip"
    )

@app.get("/api/profiles/export-bundle")
def export_profile_bundle(profile_id: Optional[str] = None):
    """Export complete bundle (vocabulary.json + LoRA weights) for a profile as a zip archive."""
    import shutil
    import tempfile

    if not profile_id:
        profile_id = db.get_active_profile().get("id", "default")
    clean_id = profile_id.strip().lower()

    temp_bundle_dir = tempfile.mkdtemp()
    bundle_root = Path(temp_bundle_dir) / f"profile_{clean_id}"
    bundle_root.mkdir(parents=True, exist_ok=True)

    # 1. Copy vocabulary.json
    if clean_id == "default":
        vocab_path = settings.VOCABULARY_PATH
    else:
        vocab_path = settings.DATA_DIR / "profiles" / clean_id / "vocabulary.json"

    if vocab_path.exists():
        shutil.copy2(str(vocab_path), str(bundle_root / "vocabulary.json"))
    else:
        with open(bundle_root / "vocabulary.json", "w", encoding="utf-8") as f:
            f.write("[]")

    # 2. Copy LoRA adapter weights if available
    adapter_path = settings.ADAPTERS_DIR / clean_id
    if not adapter_path.exists() and clean_id == "default":
        legacy = settings.ADAPTERS_DIR / "lora_latest"
        if legacy.exists():
            adapter_path = legacy

    if adapter_path.exists():
        adapter_dest = bundle_root / "lora_adapter"
        shutil.copytree(str(adapter_path), str(adapter_dest), dirs_exist_ok=True)

    # 3. Create zip archive
    zip_path = shutil.make_archive(os.path.join(temp_bundle_dir, f"local_asr_profile_{clean_id}"), "zip", str(bundle_root))

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"local_asr_profile_{clean_id}.zip"
    )

@app.post("/api/vocabulary/import")
async def import_vocabulary(file: UploadFile = File(...)):
    """Import a vocabulary.json file."""
    import json
    try:
        content = await file.read()
        parsed = json.loads(content.decode("utf-8"))
        if not isinstance(parsed, list):
            raise ValueError("Root JSON must be a list of vocabulary objects")
        vocab_mgr.save(parsed)
        return {"status": "success", "count": len(parsed)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import vocabulary: {str(e)}")

@app.websocket("/api/ws/streaming-transcribe")
async def websocket_streaming_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for real-time live streaming audio dictation.
    Accepts binary PCM float32/int16 audio chunks or JSON control messages.
    Returns: {"event": "partial_text", "text": "...", "is_final": bool}
    """
    import numpy as np
    await websocket.accept()
    audio_buffer = []
    accumulated_samples = 0
    sample_rate = 16000
    last_partial = ""

    # Fetch context vocabulary
    vocab_ctx = ""
    try:
        if vocab_mgr:
            vocab_ctx = vocab_mgr.get_context_string()
    except Exception:
        pass

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                raw_bytes = msg["bytes"]
                # Convert raw incoming bytes (float32 mono PCM 16kHz)
                try:
                    chunk = np.frombuffer(raw_bytes, dtype=np.float32)
                except Exception:
                    chunk = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

                if len(chunk) > 0:
                    audio_buffer.append(chunk)
                    accumulated_samples += len(chunk)

                # Every ~0.6s (9600 samples) or more, run bounded sliding transcribe
                if accumulated_samples >= int(sample_rate * 0.6):
                    # Only concatenate the recent 3.5 seconds (56,000 samples) for live preview
                    max_window_samples = int(sample_rate * 3.5)
                    needed_chunks = []
                    sample_cnt = 0
                    for c in reversed(audio_buffer):
                        needed_chunks.append(c)
                        sample_cnt += len(c)
                        if sample_cnt >= max_window_samples:
                            break
                    needed_chunks.reverse()
                    window_wav = np.concatenate(needed_chunks, axis=0)
                    if len(window_wav) > max_window_samples:
                        window_wav = window_wav[-max_window_samples:]

                    partial = engine.transcribe_sliding_chunk(
                        window_wav,
                        sample_rate=sample_rate,
                        max_window_sec=3.5,
                        context=vocab_ctx
                    )
                    if partial and partial != last_partial:
                        last_partial = partial
                        await websocket.send_json({
                            "event": "partial_text",
                            "text": partial,
                            "is_final": False
                        })
            elif "text" in msg and msg["text"]:
                try:
                    payload = json.loads(msg["text"])
                    event = payload.get("event")
                    if event == "finish":
                        if audio_buffer:
                            full_wav = np.concatenate(audio_buffer, axis=0)
                            final_text = engine.transcribe(full_wav, sample_rate=sample_rate, context=vocab_ctx)
                            await websocket.send_json({
                                "event": "final_text",
                                "text": final_text,
                                "is_final": True
                            })
                        else:
                            await websocket.send_json({
                                "event": "final_text",
                                "text": "",
                                "is_final": True
                            })
                        audio_buffer = []
                        accumulated_samples = 0
                        last_partial = ""
                    elif event == "reset":
                        audio_buffer = []
                        accumulated_samples = 0
                        last_partial = ""
                        await websocket.send_json({"event": "reset_ack"})
                except Exception as e:
                    print(f"[WebSocket] Error parsing control message: {e}")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Streaming error: {e}")

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
