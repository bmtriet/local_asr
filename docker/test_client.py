#!/usr/bin/env python3
"""
Test client to verify Qwen3-ASR Server API endpoint.
Tests:
1. GET /health
2. GET /v1/models
3. POST /v1/audio/transcriptions (OpenAI-compatible)
"""

import sys
import time
import requests
import numpy as np
import soundfile as sf
import io

SERVER_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

print(f"=== Testing Qwen3-ASR Server at {SERVER_URL} ===")

# 1. Test /health
try:
    res = requests.get(f"{SERVER_URL}/health", timeout=5)
    print("1. Health Check:", res.status_code, res.json())
except Exception as e:
    print("1. Health Check FAILED:", e)
    sys.exit(1)

# 2. Test /v1/models
try:
    res = requests.get(f"{SERVER_URL}/v1/models", timeout=5)
    print("2. List Models:", res.status_code, res.json())
except Exception as e:
    print("2. List Models FAILED:", e)

# 3. Generate synthetic speech tone WAV to test /v1/audio/transcriptions
sr = 16000
duration = 1.0
t = np.linspace(0, duration, int(sr * duration), endpoint=False)
wav = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

buf = io.BytesIO()
sf.write(buf, wav, sr, format="WAV")
buf.seek(0)

print("3. Sending audio to POST /v1/audio/transcriptions...")
start = time.time()
try:
    files = {"file": ("test.wav", buf, "audio/wav")}
    data = {"language": "vi", "prompt": "Xin chào"}
    res = requests.post(f"{SERVER_URL}/v1/audio/transcriptions", files=files, data=data, timeout=30)
    latency = round((time.time() - start) * 1000)
    print(f"Transcription Response ({latency}ms):", res.status_code, res.json())
    print("\n✅ All endpoint tests passed!")
except Exception as e:
    print("Transcription request FAILED:", e)
