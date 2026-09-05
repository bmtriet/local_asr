# Qwen3-ASR 0.6B Docker Container & API Endpoint

Docker container độc lập phục vụ mô hình **Qwen3-ASR-0.6B** qua REST API và WebSocket, tương thích chuẩn **OpenAI Audio Transcriptions API** (`/v1/audio/transcriptions`).

---

## 1. Khởi động Nhanh với Docker Compose (GPU Khuyên dùng)

Yêu cầu máy chủ cài sẵn **Docker** và **NVIDIA Container Toolkit** (nếu dùng GPU).

```bash
cd docker
docker compose up -d
```

Xem log khởi động:
```bash
docker compose logs -f
```

---

## 2. Build & Chạy Thủ công (Docker CLI)

### Chạy với NVIDIA GPU:
```bash
cd docker
docker build -t qwen3-asr-server:latest -f Dockerfile .
docker run -d --name qwen3-asr-api \
  --gpus all \
  -p 8000:8000 \
  -v qwen3_asr_cache:/root/.cache/huggingface \
  qwen3-asr-server:latest
```

### Chạy chế độ CPU-Only (không có GPU):
```bash
cd docker
docker build -t qwen3-asr-server:cpu -f Dockerfile.cpu .
docker run -d --name qwen3-asr-api \
  -p 8000:8000 \
  -v qwen3_asr_cache:/root/.cache/huggingface \
  qwen3-asr-server:cpu
```

---

## 3. Các API Endpoints

### 3.1. Health Check
```bash
curl http://localhost:8000/health
```
Phản hồi:
```json
{
  "status": "healthy",
  "model": "Qwen/Qwen3-ASR-0.6B",
  "device": "cuda:0",
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 5060 Ti"
}
```

### 3.2. OpenAI-Compatible Audio Transcription (`POST /v1/audio/transcriptions`)
Hỗ trợ mọi định dạng âm thanh (`wav`, `mp3`, `ogg`, `m4a`, `flac`):

```bash
curl -X POST "http://localhost:8000/v1/audio/transcriptions" \
  -F "file=@audio.wav" \
  -F "language=vi" \
  -F "prompt=Chuyên ngành y tế, công nghệ"
```

Phản hồi:
```json
{
  "text": "Xin chào đây là bài phát biểu thử nghiệm.",
  "duration": 3.45,
  "language": "vi"
}
```

### 3.3. Sử dụng với thư viện Python `openai`
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://<server-ip>:8000/v1",
    api_key="none"
)

with open("speech.wav", "rb") as audio_file:
    transcript = client.audio.transcriptions.create(
        model="Qwen/Qwen3-ASR-0.6B",
        file=audio_file,
        language="vi"
    )
    print(transcript.text)
```

### 3.4. WebSocket Streaming (`ws://localhost:8000/api/ws/transcribe`)
- Gửi các binary chunk 16kHz PCM (16-bit Mono).
- Nhận phản hồi thời gian thực qua sliding window $\le 250\text{ms}$:
  ```json
  {"event": "partial_text", "text": "Hôm nay thời tiết", "is_final": false}
  ```
- Kết thúc utterance bằng text message: `{"event": "finish"}` để nhận bản dịch / phiên âm hoàn chỉnh:
  ```json
  {"event": "final_text", "text": "Hôm nay thời tiết rất đẹp.", "is_final": true}
  ```

---

## 4. Tích hợp lại vào Ứng dụng Desktop Local ASR

Khi bạn đã deploy container này lên một máy chủ khác (ví dụ: `http://192.168.1.50:8000`), trên máy cá nhân bạn chỉ cần:
1. Mở Web UI: `http://localhost:8000`.
2. Chuyển cấu hình ASR sang:
   - **ASR Provider**: `Remote API Endpoint`
   - **Endpoint**: `http://192.168.1.50:8000/v1/audio/transcriptions`
3. Máy cá nhân sẽ giải phóng hoàn toàn VRAM/RAM và gửi âm thanh sang server để nhận diện.
