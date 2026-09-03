import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import get_settings
from storage.database import Database
from asr_engine.engine import ASREngine
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

class CorrectionRequest(BaseModel):
    corrected_text: str

class SettingsUpdateRequest(BaseModel):
    hotkey: Optional[str] = None

@app.get("/api/status")
def get_status():
    return {
        "status": "ok",
        "model": settings.MODEL_NAME,
        "device": engine.device,
        "is_model_loaded": engine.is_loaded,
        "active_lora": engine.active_adapter_name
    }

@app.get("/api/history")
def get_history(
    page: int = 1,
    limit: int = 10,
    filter_type: str = "all",
    search: str = ""
):
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit
    total = db.get_transcriptions_count(filter_type=filter_type, search=search)
    items = db.get_transcriptions(limit=limit, offset=offset, filter_type=filter_type, search=search)
    total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
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
    pending_samples = len(db.get_samples_for_training())
    status["pending_samples"] = pending_samples
    return status

@app.post("/api/train/start")
def start_train(epochs: int = 3, lr: float = 1e-4):
    def on_complete(adapter_dir):
        try:
            engine.load_lora_adapter(adapter_dir)
        except Exception as e:
            print("Failed to auto-reload LoRA adapter:", e)

    started = trainer.start_training(epochs=epochs, lr=lr, on_completed=on_complete)
    if not started:
        raise HTTPException(status_code=400, detail=trainer.last_error or "Cannot start training")
    return {"status": "started"}

@app.get("/api/settings")
def get_current_settings():
    saved_hotkey = db.get_setting("hotkey")
    active_hotkey = saved_hotkey or settings.HOTKEY
    return {
        "hotkey": active_hotkey,
        "sample_rate": settings.SAMPLE_RATE,
        "model_name": settings.MODEL_NAME,
        "device": engine.device
    }

@app.post("/api/settings")
def update_settings(payload: SettingsUpdateRequest):
    if payload.hotkey:
        cleaned_hotkey = payload.hotkey.strip().lower()
        settings.HOTKEY = cleaned_hotkey
        db.set_setting("hotkey", cleaned_hotkey)
    return {"status": "updated", "settings": get_current_settings()}

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
