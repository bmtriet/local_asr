# Local ASR & Voice Typing Daemon (Cross-Platform)

Hệ thống nhận diện giọng nói và gõ văn bản cục bộ (**Local ASR Voice Typing**) hiệu năng cao, hoạt động 100% offline không cần internet. Tích hợp mô hình nhận dạng âm học tiên tiến **Qwen3-ASR (0.6B)**, mô hình chuẩn hóa ngữ pháp & dịch thuật **Qwen2.5 (0.5B)**, module chuẩn hóa số **Vietnamese ITN**, cùng cơ chế học tăng cường liên tục (**Continual LoRA Fine-Tuning**) và **Hotword Context Biasing**.

Hỗ trợ đa nền tảng hoàn hảo trên cả **Linux**, **macOS** và **Windows** (tự động tối ưu cho cả **NVIDIA GPU**, **Apple Silicon MPS** và **CPU-Only**).

---

## 🌟 Tính năng nổi bật

- 🎙️ **Thu âm tức thì không độ trễ (Zero-Latency Recording)**: Bấm phím tắt là mic bắt đầu ghi âm ngay lập tức, không mất chữ đầu câu.
- 🚀 **Chuẩn hóa số tiếng Việt siêu tốc (Vietnamese ITN)**: Tự động phát hiện và chuyển đổi chuỗi số đọc (số điện thoại, mã OTP, số thẻ, giờ phút, phần trăm) sang chữ số tự nhiên trong 0.001s:
  - *"Không chín tám bảy ba một một tám sáu một"* $\rightarrow$ **`0987311861`**
  - *"Mã thẻ một chín hai một"* $\rightarrow$ **`Mã thẻ 1921`**
  - *"Mười sáu giờ ba mươi phút"* $\rightarrow$ **`16:30`**
- 🌐 **Hộp thoại OSD chọn ngôn ngữ & Dịch thuật**:
  - `[E]`: 🇬🇧 Dịch sang Tiếng Anh.
  - `[Z]`: 🇨🇳 Dịch sang Tiếng Trung (Phồn thể).
  - `[Phím cách / Sau 2s]`: Tự động ẩn OSD và tiếp tục ghi âm chế độ gốc.
  - `[ESC]`: ❌ Hủy bỏ ngay lập tức ở cả giai đoạn chọn chế độ lẫn khi đang ghi âm.
- 📝 **Tùy chọn xuất song ngữ (Add Origin Phrase)**: Tùy chọn in kèm câu nói nguồn và bản dịch trên 2 dòng để tiện đối chiếu.
- 🧠 **Bộ nhớ từ vựng ưu tiên (Hotword Context Biasing)**: Tự động trích xuất các từ bạn đã sửa (tên riêng, từ viết tắt như `Qwen`, `ASR`, dãy số...) nạp thẳng vào context prompt của mô hình để nhận diện đúng ngay từ lần nói sau.
- 🎯 **Huấn luyện LoRA thực tế (Real PyTorch LoRA Fine-Tuning)**: Fine-tune trực tiếp trên các mẫu ghi âm đã review, tự động cập nhật và nạp trọng số LoRA mới (`adapter_model.safetensors`) lên GPU ngay trong phiên chạy.
- 🔄 **System Tray Indicator**: Khay hệ thống đổi màu động theo trạng thái (Idle, Recording, Transcribing), hỗ trợ mở Web UI, Restart App và Thoát.

---

## 🐧 1. Hướng dẫn Cài đặt & Chạy trên Linux (Ubuntu / Debian / Fedora / Arch)

### Bước 1: Cài đặt thư viện hệ thống
Mở Terminal và cài đặt các gói hỗ trợ âm thanh và bàn phím:

```bash
# Trên Ubuntu / Debian:
sudo apt update
sudo apt install -y python3-venv python3-pip portaudio19-dev xclip xdotool libgtk-3-dev libayatana-appindicator3-dev

# Trên Fedora:
sudo dnf install -y portaudio-devel xclip xdotool gtk3-devel libappindicator-gtk3-devel

# Trên Arch Linux:
sudo pacman -S portaudio xclip xdotool gtk3 libappindicator-gtk3
```

### Bước 2: Tạo môi trường ảo & Cài đặt thư viện Python
```bash
# Di chuyển vào thư mục dự án
cd local_asr

# Khởi tạo môi trường ảo Python
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt PyTorch:
# Nếu có NVIDIA GPU (CUDA):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Nếu chỉ dùng CPU (không có GPU):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Cài đặt các gói phụ thuộc
pip install -r requirements.txt
```

### Bước 3: Khởi động ứng dụng
- **Chạy ngầm hoàn toàn (Khuyên dùng):**
  ```bash
  ./start.sh
  ```
  *(Ứng dụng sẽ chạy trong nền, xuất hiện icon ở khay hệ thống và ghi nhật ký vào `logs/app.log`)*.

- **Chạy chế độ Debug xem log trực tiếp:**
  ```bash
  ./start.sh --foreground
  ```

- **Dừng ứng dụng:** Nhấp chuột phải vào Tray Icon chọn **Exit**, hoặc chạy lệnh:
  ```bash
  pkill -f "local_asr/main.py"
  ```

---

## 🍎 2. Hướng dẫn Cài đặt & Chạy trên macOS (Apple Silicon M1/M2/M3/M4 & Intel)

### Bước 1: Cài đặt Homebrew & Thư viện âm thanh
Nếu máy chưa có Homebrew, hãy cài đặt [Homebrew](https://brew.sh/). Sau đó chạy:

```bash
brew install portaudio
```

### Bước 2: Tạo môi trường ảo & Cài đặt thư viện Python
```bash
# Di chuyển vào thư mục dự án
cd local_asr

# Khởi tạo môi trường ảo Python 3.10+
python3 -m venv .venv
source .venv/bin/activate

# Nâng cấp pip
pip install --upgrade pip

# Cài đặt PyTorch (Bản chính thức hỗ trợ sẵn MPS Acceleration cho chip M1/M2/M3/M4)
pip install torch torchvision torchaudio

# Cài đặt các thư viện dự án
pip install -r requirements.txt
```

### Bước 3: Cấp quyền hệ thống cho macOS (Rất quan trọng!)
macOS có cơ chế bảo mật nghiêm ngặt. Để ứng dụng có thể bắt phím tắt toàn cục và thu âm micro:
1. Mở **System Settings (Cài đặt hệ thống)** $\rightarrow$ **Privacy & Security (Quyền riêng tư & Bảo mật)**.
2. Mục **Microphone**: Bật cấp quyền cho ứng dụng **Terminal** (hoặc iTerm2 / VSCode).
3. Mục **Accessibility (Trợ năng)**: Thêm và bật cấp quyền cho ứng dụng **Terminal** (hoặc iTerm2) để cho phép phần mềm nhận phím tắt và dán văn bản tự động.
4. Mục **Input Monitoring (Giám sát đầu vào)**: Cấp quyền cho Terminal nếu hệ điều hành yêu cầu.

### Bước 4: Khởi động ứng dụng
```bash
source .venv/bin/activate
python main.py --service all
```

---

## 🪟 3. Hướng dẫn Cài đặt & Chạy trên Windows (Windows 10 / 11, 64-bit)

### Cách 1: Cài đặt tự động 1-Click (Khuyên dùng)
1. Đảm bảo máy đã cài đặt [Python 3.10+](https://www.python.org/downloads/) (Khi cài đặt, **BẮT BUỘC tick chọn "Add python.exe to PATH"**).
2. Nhấp đúp chuột vào file:
   ```text
   setup_windows.bat
   ```
3. Script cài đặt sẽ tự động hoàn toàn:
   - Tạo môi trường ảo `.venv`.
   - Kiểm tra card đồ họa NVIDIA. Nếu có GPU sẽ tải PyTorch CUDA, nếu không có GPU sẽ tự động tải bản PyTorch CPU siêu nhẹ (~200MB thay vì 3GB).
   - Cài đặt đầy đủ các gói thư viện tương thích Windows.
   - Hỏi bạn có muốn tạo lối tắt tự khởi động cùng Windows (`shell:startup`) hay không.

### Cách 2: Cài đặt thủ công qua CMD / PowerShell
```cmd
cd local_asr
python -m venv .venv
.\.venv\Scripts\activate

:: Có GPU NVIDIA:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

:: Không có GPU (CPU-Only):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

:: Cài đặt thư viện:
pip install -r requirements.txt
```

### Khởi động ứng dụng trên Windows
- **Chạy ngầm hoàn toàn (Không hiện cửa sổ đen CMD):**
  Nhấp đúp vào:
  ```text
  start.vbs
  ```
- **Chạy chế độ Debug (Hiện cửa sổ CMD để xem nhật ký log):**
  Nhấp đúp vào:
  ```text
  start.bat
  ```

---

## 🖥️ 4. Hướng dẫn Sử dụng Giao diện Web (Dashboard)

Truy cập giao diện quản trị Web tại địa chỉ:
👉 **`http://127.0.0.1:8000`**

Giao diện Web hoàn toàn bằng Tiếng Anh với các chức năng chính:
1. **Recognition History & Corrections**:
   - Nghe lại các file âm thanh đã thu âm.
   - Sửa lại câu nhận diện (Ground Truth) để mô hình học theo phong cách gõ của bạn.
   - Bấm **Save Review** để lưu lại câu sửa lỗi.
2. **LoRA Fine-Tuning**:
   - Theo dõi số lượng mẫu chờ huấn luyện (`pending_samples`).
   - Bấm **Start LoRA Training** để kích hoạt quá trình fine-tuning trọng số thực tế trên GPU. Trọng số mới sẽ được nạp tự động vào máy ngay khi train xong.
3. **Settings**:
   - Đổi phím tắt toàn cục (Global Shortcut).
   - Bật/Tắt tính năng chuẩn hóa và sửa lỗi bằng AI (**Grammar Correction**).
   - Bật/Tắt chế độ xuất song ngữ (**Add origin phrase**).

---

## ⚙️ 5. Tùy biến Cấu hình (config.py)

Bạn có thể chỉnh sửa các giá trị mặc định trong file [config.py](config.py) hoặc thông qua biến môi trường:

| Tham số | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `HOTKEY` | `f9` | Phím tắt kích hoạt thu âm (`f9`, `alt+z`, `ctrl+space`,...) |
| `MODEL_NAME` | `Qwen/Qwen3-ASR-0.6B` | Mô hình nhận dạng giọng nói ASR |
| `GRAMMAR_MODEL_NAME`| `Qwen/Qwen2.5-0.5B-Instruct` | Mô hình LLM sửa ngữ pháp & dịch thuật |
| `HOST` | `127.0.0.1` | Địa chỉ IP Web UI Server |
| `PORT` | `8000` | Cổng dịch vụ Web UI |
| `CPU_THREADS` | `4` | Số luồng CPU tối đa sử dụng khi không có GPU (tránh giật lag máy) |
| `ADD_ORIGIN_PHRASE` | `False` | Xuất cả câu gốc lẫn câu dịch khi bấm phím dịch |

---

## 🧪 6. Chạy Kiểm thử (Unit Tests)

Dự án đi kèm bộ kiểm thử tự động toàn diện kiểm tra mọi tính năng (Cross-platform, ITN Normalizer, LoRA Training, API, Tray Indicator):

```bash
# Kích hoạt virtualenv và chạy pytest:
PYTHONPATH=. pytest
```
*(Toàn bộ 24/24 test cases đều được bảo đảm vượt qua 100%).*
