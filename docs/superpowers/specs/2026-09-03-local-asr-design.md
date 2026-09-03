# Architecture Design: Local ASR Voice Typing & Personalization (Qwen3-ASR-0.6B)

## 1. Overview & Mục tiêu
Xây dựng hệ thống Speech-to-Text (ASR) chạy hoàn toàn cục bộ (offline/local) trên máy trạm Linux (GPU RTX 5060 Ti 16GB, X11):
- **Core Engine**: Sử dụng mô hình `Qwen3-ASR-0.6B` cho tốc độ nhận dạng siêu nhanh (< 200ms) và độ chính xác cao đối với tiếng Việt và đa ngôn ngữ.
- **Voice Typing Daemon**: Lắng nghe phím tắt toàn cục (mặc định `Ctrl+Alt+Space`, có thể cấu hình lại) theo chế độ toggle hoặc push-to-talk.
- **Visual Feedback**: Tray icon trên khay hệ thống (System Tray via AppIndicator / PyStray) chuyển màu và hiệu ứng trạng thái (Idle -> Recording / Animated -> Processing).
- **Text Injection**: Gõ trực tiếp văn bản vừa nhận dạng vào ô input/con trỏ đang active thông qua `xdotool` (hoặc clipboard paste mô phỏng phím).
- **Personalization & Continual Learning (LoRA)**:
  - Tự động lưu bản ghi âm và kết quả nhận dạng vào cơ sở dữ liệu SQLite local.
  - Web UI hiện đại (FastAPI + Vanilla HTML/CSS/JS dark mode cao cấp) cho phép xem lại lịch sử, nghe lại audio, highlight & sửa các từ sai.
  - Hỗ trợ cơ chế **Fine-tuning LoRA định kỳ**: Gom các cặp (audio, corrected_text) thành dataset để chạy LoRA fine-tune cục bộ, sau đó load LoRA adapter vào model phục vụ suy luận mà không cần train lại toàn bộ base model.
- **Extensible Backend API**: Cung cấp REST/WebSocket API để các ứng dụng khác gửi audio file hoặc stream audio nhận text.

---

## 2. Kiến trúc Hệ thống (System Architecture)

```
       [ Micro / arecord ]
                │
                ▼
   ┌────────────────────────┐         Global Hotkey (Ctrl+Alt+Space)
   │   Audio Capture Daemon  │ ◄────── Tray Icon Animated Feedback
   └──────────┬─────────────┘
              │ (WAV chunk)
              ▼
   ┌────────────────────────┐
   │  ASR Inference Engine   │ ◄────── Qwen3-ASR-0.6B Base Model
   │  (PyTorch / HF / vLLM)  │ ◄────── Active LoRA Adapter (Fine-tuned)
   └──────────┬─────────────┘
              │ (Transcribed Text)
              ▼
   ┌────────────────────────┬──────────────────────────────────────────┐
   │  Active Window Inject   │                                          │
   │  (xdotool / Clipboard)  │                                          │
   └────────────────────────┘                                          │
                                                                       ▼
                                                          ┌───────────────────────────┐
                                                          │ SQLite Database           │
                                                          │ (Audio clips + Text logs) │
                                                          └─────────────┬─────────────┘
                                                                        │
                                                                        ▼
   ┌──────────────────────────────────────────────────┐        ┌──────────────────────┐
   │ FastAPI Web Server + Modern Web UI               │ ◄─────┤ Dataset Builder &    │
   │ - History Review & Audio Playback                │       │ LoRA Training Runner │
   │ - Label & Correction Editor                      │       │ (PEFT / HuggingFace) │
   │ - Trigger LoRA Fine-tune & Monitor Loss          │       └──────────────────────┘
   │ - Settings (Hotkeys, Audio Device, Sensitivity)  │
   └──────────────────────────────────────────────────┘
```

---

## 3. Chi tiết các thành phần (Component Breakdown)

### 3.1. ASR Engine (`asr_engine/`)
- Quản lý nạp model `Qwen/Qwen3-ASR-0.6B` trên GPU CUDA (RTX 5060 Ti).
- Tích hợp `peft` để nạp / reload dynamic LoRA adapter khi người dùng train xong adapter mới.
- Cung cấp hàm `transcribe(audio_path_or_bytes) -> str` hỗ trợ xử lý audio 16kHz mono.

### 3.2. Voice Typing & System Tray Daemon (`daemon/`)
- **Global Hotkey Listener**: Bắt tổ hợp phím (mặc định `Ctrl+Alt+Space`) sử dụng `pynput` hoặc `keyboard` / `Xlib`. Có thể tùy chỉnh phím trong config.
- **Tray Indicator**: Sử dụng `pystray` tạo icon khay hệ thống:
  - Trạng thái **Idle**: Icon màu xanh dịu / mic xám.
  - Trạng thái **Recording**: Icon nhấp nháy đỏ / waveform animation.
  - Trạng thái **Transcribing**: Icon vàng / xoay vòng.
- **Audio Recorder**: Ghi âm chất lượng cao từ microphone qua `sounddevice` / `pyaudio` hoặc subprocess `arecord`.
- **Auto Injector**: Sau khi có kết quả text, dùng `xdotool type --clearmodifiers` hoặc copy vào X11 clipboard và simulate `Ctrl+V` (giữ nguyên đầy đủ dấu tiếng Việt Unicode không bị nuốt ký tự).

### 3.3. Database & Dataset Storage (`storage/`)
- Thư mục lưu audio: `data/recordings/<uuid>.wav`.
- SQLite database (`data/local_asr.db`):
  - Bảng `transcriptions`: `id, timestamp, audio_path, duration, raw_text, corrected_text, is_reviewed, used_in_training`.
  - Bảng `settings`: Lưu config phím tắt, audio device, LoRA hyperparameters, v.v.

### 3.4. LoRA Fine-Tuning Pipeline (`training/`)
- Bộ lọc dataset: Gom các bản ghi có `is_reviewed = 1` và `corrected_text != raw_text` (kết hợp các mẫu đúng).
- Script fine-tune với Hugging Face `transformers` + `peft` (LoRA `r=8` hoặc `16`, `lora_alpha=32`, `target_modules=["q_proj", "v_proj"]`).
- Quá trình train chạy ở background process, log metric (loss, step) để cập nhật thời gian thực lên Web UI.
- Tự động checkpoint và reload adapter vào Inference Engine sau khi hoàn thành.

### 3.5. FastAPI Backend & Web UI (`web/`)
- **REST Endpoints**:
  - `GET /api/history`: Danh sách các câu ghi âm gần nhất, trạng thái sửa.
  - `POST /api/history/{id}/correct`: Lưu bản sửa từ đúng của người dùng.
  - `GET /api/audio/{id}`: Stream file âm thanh để nghe lại trực tiếp trên web.
  - `POST /api/train/start`: Kích hoạt tiến trình LoRA fine-tuning.
  - `GET /api/train/status`: Theo dõi tiến độ loss / epoch theo thời gian thực.
  - `POST /api/v1/transcribe`: API public cho các ứng dụng khác gửi audio vào nhận text.
  - `GET /api/settings` & `POST /api/settings`: Lưu cấu hình phím tắt và tham số.
- **Web UI**:
  - Giao diện Dark Mode cao cấp (Glassmorphism, font Inter, màu nhấn Electric Indigo & Emerald).
  - Waveform audio player mini cho từng dòng lịch sử.
  - Trình soạn thảo inline: Click vào từ nhận sai để sửa trực tiếp và nhấn `Enter` để lưu.
  - Bảng điều khiển LoRA Trainer trực quan: Hiển thị số lượng mẫu sửa sẵn sàng train, nút "Bắt đầu huấn luyện", biểu đồ/thanh tiến trình loss trực tiếp.

---

## 4. Xác minh & Kiểm thử (Verification Plan)
1. **Kiểm tra môi trường**: Test GPU CUDA, PyTorch, PyStray, Xdotool trong môi trường Python ảo venv.
2. **Kiểm tra Model Inference**: Download weights `Qwen3-ASR-0.6B`, chạy thử đoạn audio mẫu tiếng Việt, kiểm tra thời gian suy luận (latency) và VRAM usage.
3. **Kiểm tra Hotkey & Typing**: Kích hoạt `Ctrl+Alt+Space`, nói 1 câu -> kiểm tra tray icon đổi màu -> kiểm tra text được tự động gõ vào trình soạn thảo đang mở.
4. **Kiểm tra Web UI**: Mở Web UI trên trình duyệt cục bộ `http://localhost:8000`, nghe lại audio, sửa từ sai, kiểm tra API lưu trữ.
5. **Kiểm tra LoRA Trainer**: Chạy thử một lượt LoRA train giả lập với 3-5 mẫu dữ liệu sửa để đảm bảo pipeline lưu adapter và reload thành công.
