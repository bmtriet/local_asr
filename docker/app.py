import os
import io
import time
import tempfile
import asyncio
import torch
import numpy as np
import soundfile as sf
import scipy.signal
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Dict, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configuration from environment variables
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3-ASR-0.6B")
DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
TORCH_DTYPE = os.getenv("TORCH_DTYPE", "bfloat16")
PORT = int(os.getenv("PORT", "9001"))
HOST = os.getenv("HOST", "0.0.0.0")
API_KEY = os.getenv("API_KEY", "")
ADAPTERS_DIR = Path(os.getenv("ADAPTERS_DIR", "/app/adapters"))
ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)

dtype = getattr(torch, TORCH_DTYPE, torch.bfloat16)
if DEVICE == "cpu":
    dtype = torch.float32

print(f"[ASR Server] Initializing model: {MODEL_NAME} on {DEVICE} ({dtype})...")

from qwen_asr import Qwen3ASRModel, parse_asr_output

device_map = "cuda:0" if "cuda" in DEVICE and torch.cuda.is_available() else "cpu"
if "cuda" in device_map:
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

model = Qwen3ASRModel.from_pretrained(
    MODEL_NAME,
    dtype=dtype,
    device_map=device_map
)
print(f"[ASR Server] Model loaded successfully on {device_map}.")

class DynamicAdapterManager:
    """
    Manages in-memory LoRA adapters for multi-profile/multi-tenant requests.
    Enables concurrent hot-switching of adapters on a single base model.
    """
    def __init__(self, qwen_model, adapters_dir: Path):
        self.qwen_model = qwen_model
        self.adapters_dir = adapters_dir
        self.loaded_adapters = set()
        self.active_adapter: Optional[str] = None
        self.lock = asyncio.Lock()
        self._target_thinker = self._resolve_thinker_model()

    def _resolve_thinker_model(self):
        raw_model = getattr(self.qwen_model, "model", self.qwen_model)
        thinker = getattr(raw_model, "thinker", None)
        if thinker is not None:
            return getattr(thinker, "model", thinker)
        return raw_model

    def list_disk_adapters(self) -> List[Dict[str, str]]:
        """List all LoRA adapters available in storage."""
        res = []
        if not self.adapters_dir.exists():
            return res
        for item in self.adapters_dir.iterdir():
            if item.is_dir():
                has_config = (item / "adapter_config.json").exists()
                has_weights = (item / "adapter_model.safetensors").exists() or (item / "adapter_model.bin").exists()
                if has_config and has_weights:
                    res.append({
                        "name": item.name,
                        "path": str(item),
                        "loaded_in_memory": item.name in self.loaded_adapters
                    })
        return res

    def _ensure_adapter_loaded(self, adapter_name: str) -> bool:
        """Load adapter into memory if on disk and not yet loaded."""
        if adapter_name in self.loaded_adapters:
            return True

        adapter_path = self.adapters_dir / adapter_name
        if not adapter_path.exists():
            return False

        has_config = (adapter_path / "adapter_config.json").exists()
        has_weights = (adapter_path / "adapter_model.safetensors").exists() or (adapter_path / "adapter_model.bin").exists()
        if not (has_config and has_weights):
            return False

        try:
            from peft import PeftModel
            target_model = self._resolve_thinker_model()
            if isinstance(target_model, PeftModel):
                target_model.load_adapter(str(adapter_path), adapter_name=adapter_name)
            else:
                peft_m = PeftModel.from_pretrained(target_model, str(adapter_path), adapter_name=adapter_name)
                raw_model = getattr(self.qwen_model, "model", self.qwen_model)
                if hasattr(raw_model, "thinker"):
                    raw_model.thinker.model = peft_m
                self._target_thinker = peft_m

            self.loaded_adapters.add(adapter_name)
            print(f"[ASR Server] Successfully cached LoRA adapter '{adapter_name}' in memory.")
            return True
        except Exception as e:
            print(f"[ASR Server] Error loading adapter '{adapter_name}': {e}")
            return False

    def activate_adapter(self, adapter_name: Optional[str]):
        """
        Hot-switch to requested adapter. If None or empty or not found, disables adapters
        and falls back cleanly to the base model.
        """
        from peft import PeftModel
        target_model = self._resolve_thinker_model()
        if not isinstance(target_model, PeftModel):
            return

        if not adapter_name or adapter_name.strip() in ("", "default", "none", "base"):
            if hasattr(target_model, "disable_adapters"):
                target_model.disable_adapters()
            self.active_adapter = None
            return

        clean_name = adapter_name.strip()
        loaded = self._ensure_adapter_loaded(clean_name)
        if loaded:
            if hasattr(target_model, "enable_adapters"):
                target_model.enable_adapters()
            if hasattr(target_model, "set_adapter"):
                target_model.set_adapter(clean_name)
            self.active_adapter = clean_name
        else:
            if hasattr(target_model, "disable_adapters"):
                target_model.disable_adapters()
            self.active_adapter = None

adapter_manager = DynamicAdapterManager(model, ADAPTERS_DIR)

app = FastAPI(
    title="Qwen3-ASR API Server",
    description="Multi-Profile OpenAI-compatible Speech-to-Text with Dynamic LoRA and Real-time Streaming",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_audio_from_bytes(audio_bytes: bytes, target_sr: int = 16000) -> np.ndarray:
    """Reads audio bytes from any supported format (wav, mp3, ogg, etc.) into 16kHz float32 numpy array."""
    with io.BytesIO(audio_bytes) as buf:
        wav, sr = sf.read(buf)
    if sr != target_sr:
        num_samples = round(len(wav) * float(target_sr) / sr)
        wav = scipy.signal.resample(wav, num_samples)
    if len(wav.shape) > 1:
        wav = wav.mean(axis=1)
    return wav.astype(np.float32)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "device": device_map,
        "gpu_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None"
    }

@app.get("/v1/models")
def list_models():
    """OpenAI-compatible models list endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_NAME,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "qwen"
            }
        ]
    }

@app.get("/v1/adapters")
def list_adapters():
    """List all available LoRA adapters on the server and their in-memory load state."""
    return {
        "adapters": adapter_manager.list_disk_adapters(),
        "active_adapter": adapter_manager.active_adapter
    }

@app.post("/v1/adapters/upload")
async def upload_adapter(
    file: UploadFile = File(...),
    adapter_name: Optional[str] = Form(None)
):
    """Upload a LoRA adapter zip archive (containing adapter_config.json and adapter_model.safetensors)."""
    try:
        content = await file.read()
        z = zipfile.ZipFile(io.BytesIO(content), "r")
        namelist = z.namelist()

        has_config = any(n.endswith("adapter_config.json") for n in namelist)
        has_weights = any(n.endswith("adapter_model.safetensors") or n.endswith("adapter_model.bin") for n in namelist)
        if not (has_config and has_weights):
            raise HTTPException(status_code=400, detail="Zip file must contain adapter_config.json and adapter_model.safetensors/bin")

        clean_name = (adapter_name or "").strip().lower()
        if not clean_name:
            # Infer from root directory in zip or filename
            for n in namelist:
                if "/" in n:
                    clean_name = n.split("/")[0].replace("lora_adapter_", "").replace("lora_", "")
                    break
        if not clean_name:
            clean_name = file.filename.replace(".zip", "").replace("lora_adapter_", "").strip().lower()

        target_dir = ADAPTERS_DIR / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)

        for n in namelist:
            if n.endswith("/"):
                continue
            # Strip outer directory if present
            parts = n.split("/")
            filename = parts[-1]
            if filename in ("adapter_config.json", "adapter_model.safetensors", "adapter_model.bin", "special_tokens_map.json", "tokenizer_config.json"):
                with open(target_dir / filename, "wb") as f:
                    f.write(z.read(n))

        # Pre-load adapter into memory
        adapter_manager._ensure_adapter_loaded(clean_name)

        return {
            "status": "success",
            "adapter_name": clean_name,
            "target_dir": str(target_dir)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process adapter archive: {str(e)}")

@app.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model_name: Optional[str] = Form(None, alias="model"),
    prompt: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
    language: Optional[str] = Form("vi"),
    lora_adapter: Optional[str] = Form(None)
):
    """
    OpenAI-compatible audio transcription endpoint with Multi-Profile Dynamic LoRA support.
    Accepts multipart/form-data with an audio file, optional context prompt, and lora_adapter name.
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio file provided.")

        wav = load_audio_from_bytes(content, target_sr=16000)
        duration = len(wav) / 16000.0

        context_str = prompt or ""
        adapter_tag = lora_adapter.strip() if lora_adapter else "base"
        print(f"[ASR Server] Transcribing audio: duration={duration:.2f}s, context_len={len(context_str)}, lang={language}, lora={adapter_tag}")

        # Thread-safe lock for adapter hot-switch and inference
        async with adapter_manager.lock:
            adapter_manager.activate_adapter(lora_adapter)
            results = model.transcribe((wav, 16000), context=context_str)

        if not results:
            text = ""
        else:
            first_res = results[0]
            text = getattr(first_res, "text", "")
            if not text and isinstance(first_res, dict):
                text = first_res.get("text", "")
            text = str(text).strip()

        print(f"[ASR Server] Transcription completed: '{text}' ({duration:.2f}s, lora={adapter_tag})")

        if response_format == "text":
            return text

        return {
            "text": text,
            "duration": round(duration, 2),
            "language": language or "vi",
            "lora_adapter": adapter_manager.active_adapter
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

@app.websocket("/api/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    Real-time Live Streaming WebSocket Endpoint.
    Client streams 16kHz PCM audio chunks; server decodes trailing 3.5s window with constant latency <= 250ms.
    """
    await websocket.accept()
    audio_buffer = bytearray()
    last_transcribed = ""

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                chunk = message["bytes"]
                audio_buffer.extend(chunk)

                # Process every 0.4s of audio
                sample_count = len(audio_buffer) // 2 # 16-bit PCM = 2 bytes per sample
                if sample_count >= int(16000 * 0.4):
                    # Convert to float32
                    pcm_int16 = np.frombuffer(audio_buffer, dtype=np.int16)
                    wav = pcm_int16.astype(np.float32) / 32768.0

                    # Sliding window: slice trailing 3.5s
                    max_window = int(16000 * 3.5)
                    if len(wav) > max_window:
                        wav = wav[-max_window:]

                    # Decode sliding chunk
                    prompt = model._build_text_prompt(context="", force_language=None)
                    inputs = model.processor(text=[prompt], audio=[wav], return_tensors="pt", padding=True)
                    inputs = inputs.to(model.model.device).to(model.model.dtype)

                    with torch.no_grad():
                        text_ids = model.model.generate(
                            **inputs,
                            max_new_tokens=36,
                            pad_token_id=getattr(model.processor.tokenizer, "eos_token_id", 151645)
                        )

                    decoded = model.processor.batch_decode(
                        text_ids.sequences[:, inputs["input_ids"].shape[1]:],
                        skip_special_tokens=True,
                        clean_up_tokenization_spaces=False
                    )

                    if decoded and decoded[0]:
                        _, partial_text = parse_asr_output(decoded[0], user_language=None)
                        partial_text = partial_text.strip()
                        if partial_text and partial_text != last_transcribed:
                            last_transcribed = partial_text
                            await websocket.send_json({
                                "event": "partial_text",
                                "text": partial_text,
                                "is_final": False
                            })

            elif "text" in message and message["text"]:
                import json
                try:
                    data = json.loads(message["text"])
                    if data.get("event") == "finish":
                        # Perform final pass on entire accumulated audio
                        if len(audio_buffer) > 0:
                            pcm_int16 = np.frombuffer(audio_buffer, dtype=np.int16)
                            wav = pcm_int16.astype(np.float32) / 32768.0
                            results = model.transcribe((wav, 16000), context="")
                            final_text = ""
                            if results:
                                first_res = results[0]
                                final_text = getattr(first_res, "text", "") or (first_res.get("text", "") if isinstance(first_res, dict) else "")
                            await websocket.send_json({
                                "event": "final_text",
                                "text": str(final_text).strip(),
                                "is_final": True
                            })
                        audio_buffer.clear()
                        last_transcribed = ""
                except Exception as e:
                    print(f"[WS] Command error: {e}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
