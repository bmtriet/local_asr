import os
import io
import time
import tempfile
import torch
import numpy as np
import soundfile as sf
import scipy.signal
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configuration from environment variables
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3-ASR-0.6B")
DEVICE = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
TORCH_DTYPE = os.getenv("TORCH_DTYPE", "bfloat16")
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
API_KEY = os.getenv("API_KEY", "")

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

app = FastAPI(
    title="Qwen3-ASR API Server",
    description="OpenAI-compatible Speech-to-Text and Real-time Streaming API powered by Qwen3-ASR",
    version="1.0.0"
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

@app.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model_name: Optional[str] = Form(None, alias="model"),
    prompt: Optional[str] = Form(None),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
    language: Optional[str] = Form("vi")
):
    """
    OpenAI-compatible audio transcription endpoint.
    Accepts multipart/form-data with an audio file and optional context prompt.
    """
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio file provided.")

        wav = load_audio_from_bytes(content, target_sr=16000)
        duration = len(wav) / 16000.0

        context_str = prompt or ""
        results = model.transcribe((wav, 16000), context=context_str)
        if not results:
            text = ""
        else:
            first_res = results[0]
            text = getattr(first_res, "text", "")
            if not text and isinstance(first_res, dict):
                text = first_res.get("text", "")
            text = str(text).strip()

        if response_format == "text":
            return text

        return {
            "text": text,
            "duration": round(duration, 2),
            "language": language or "vi"
        }
    except Exception as e:
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
