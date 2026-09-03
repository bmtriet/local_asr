# Local ASR & Voice Typing Daemon (Cross-Platform)

Hệ thống nhận diện giọng nói và gõ văn bản cục bộ (Local ASR) sử dụng **Qwen3-ASR** kết hợp mô hình sửa lỗi chính tả / dịch thuật **Qwen2.5**, hỗ trợ học tăng cường liên tục (Continual Learning LoRA) và hoạt động đa nền tảng trên cả **Linux** và **Windows** (hỗ trợ cả **NVIDIA GPU** và **CPU-Only**).

---

## 🌟 Tính năng chính
- 🎙️ **Gõ văn bản bằng giọng nói tốc độ cao**: Kích hoạt bằng phím tắt toàn cục (mặc định: `Alt+Z` hoặc `Ctrl+Alt+Space`).
- 🌐 **Hộp thoại chọn chế độ dịch thuật (OSD)**:
  - `[E]`: 🇬🇧 Dịch sang Tiếng Anh.
  - `[Z]`: 🇨🇳 Dịch sang Tiếng Trung (Phồn thể).
  - `[Phím cách / Phím khác]`: 🇻🇳 Giữ nguyên ngôn ngữ gốc và tự động sửa chính tả, chuẩn hoá dấu câu.
  - `[ESC]`: ❌ Hủy bỏ ngay lập tức ở cả giai đoạn chọn chế độ lẫn khi đang ghi âm.
- 🔄 **Hệ thống Tray Icon trực quan**: Xem trạng thái (Idle, Recording, Transcribing), mở Web UI, Khởi động lại (Restart App), và Thoát (Exit).
- ⚡ **Tự động nhận diện GPU & CPU**:
  - Có GPU: Tự động kích hoạt CUDA (`bfloat16`).
  - Không có GPU (CPU-Only): Tự động chuyển sang CPU (`float32`) với điều tiết số luồng xử lý thông minh để không làm đơ máy.
- 🔕 **Chạy ngầm hoàn toàn (Headless)**: Không bao giờ bật cửa sổ đen terminal/CMD.

---

## 💻 Hướng dẫn Cài đặt & Chạy trên Windows

### 1. Cài đặt tự động (1-Click Setup)
1. Đảm bảo máy đã cài đặt [Python 3.10+](https://www.python.org/downloads/) (lưu ý tick chọn **"Add python.exe to PATH"**).
2. Nhấp đúp chuột vào file:
   ```text
   setup_windows.bat
   ```
3. Script sẽ tự động:
   - Tạo môi trường ảo `.venv`.
   - Kiểm tra card NVIDIA qua `nvidia-smi`. Nếu không có GPU, script tự động tải bản PyTorch CPU siêu nhẹ (~200MB thay vì 3GB CUDA).
   - Cài đặt đầy đủ dependencies.
   - Hỏi bạn có muốn tự động tạo lối tắt khởi động cùng Windows (`shell:startup`) hay không.

### 2. Khởi động ứng dụng
- **Chạy ngầm hoàn toàn (Không hiện cửa sổ CMD):**
  Nhấp đúp vào:
  ```text
  start.vbs
  ```
- **Chạy chế độ Debug (Hiện cửa sổ CMD để xem log):**
  Nhấp đúp vào:
  ```text
  start.bat
  ```

---

## 🐧 Hướng dẫn Cài đặt & Chạy trên Linux (Ubuntu)

### 1. Khởi động & Chạy ngầm
- Chạy script:
  ```bash
  ./start.sh
  ```
- Script sẽ tự động chạy nền không hiện terminal và ghi log vào `logs/app.log`.

### 2. Tự động khởi động cùng máy
- File desktop autostart đã được tích hợp tại:
  `~/.config/autostart/local_asr.desktop`

---

## 🛠️ Cấu hình (config.py)
Bạn có thể tùy biến các thông số trong file `config.py` hoặc qua biến môi trường:
- `HOTKEY`: Phím tắt kích hoạt (mặc định: `alt+z` hoặc `ctrl+alt+space`).
- `MODEL_NAME`: Mô hình ASR (mặc định: `Qwen/Qwen3-ASR-0.6B`).
- `GRAMMAR_MODEL_NAME`: Mô hình sửa lỗi ngữ pháp & dịch thuật (mặc định: `Qwen/Qwen2.5-0.5B-Instruct`).
- `HOST` & `PORT`: Địa chỉ Web UI Server (mặc định: `127.0.0.1:8000`).
