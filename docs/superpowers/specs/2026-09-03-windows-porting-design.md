# Specification: Porting Local ASR to Windows (GPU & CPU-Only Support)

## 1. Mục tiêu & Tổng quan
Porting hệ thống Local ASR từ Linux sang Windows hỗ trợ đa nền tảng (chạy trên cả Linux và Windows trong cùng một codebase).
Đặc biệt, hệ thống phải hoạt động tốt trên cả máy tính Windows **không có GPU (chỉ có CPU)** lẫn máy có card đồ hoạ NVIDIA GPU.

---

## 2. Kiến trúc & Các thành phần cần điều chỉnh

### 2.1. Hỗ trợ CPU-Only & Auto Hardware Detection
- **Nhận diện phần cứng tự động**:
  - Kiểm tra `torch.cuda.is_available()`.
  - Nếu có GPU: Dùng `device="cuda:0"`, `dtype=torch.bfloat16`.
  - Nếu **không có GPU (CPU-Only)**:
    - Tự động fallback sang `device="cpu"`, `dtype=torch.float32`.
    - Thiết lập giới hạn luồng CPU: `torch.set_num_threads(min(4, os.cpu_count() or 4))` nhằm tránh tình trạng nghẽn CPU 100% làm đơ máy khi ASR đang suy luận.
    - Cả 2 model (Qwen3-ASR 0.6B và Qwen2.5 0.5B-Instruct) đều có kích thước siêu nhẹ (~1.1GB RAM và ~1.0GB RAM) nên chạy hoàn toàn khả thi trên CPU của laptop/PC văn phòng.

### 2.2. Text Injection & Xóa ký tự chế độ (Cross-platform)
- **Hàm `_inject_windows(text)` trong `daemon/injector.py`**:
  - Sao chép nội dung vào Clipboard Windows qua module chuẩn hoặc Windows API (`ctypes.windll.user32`).
  - Gửi tổ hợp phím `Ctrl + V` thông qua `pynput.keyboard.Controller` hoặc `keybd_event` của Windows Win32 API.
- **Xóa ký tự chế độ (Backspace)**:
  - Thay thế lệnh gọi `xdotool` bằng hàm trừu tượng đa nền tảng:
    - Trên Windows: `pynput.keyboard.Controller().tap(keyboard.Key.backspace)`.
    - Trên Linux: Tiếp tục dùng `xdotool` hoặc `pynput`.

### 2.3. System Tray & Bàn phím toàn cục
- **System Tray (`pystray`)**:
  - `pystray` trên Windows hỗ trợ trực tiếp qua Win32 API (`Shell_NotifyIcon`), không phụ thuộc `gi` hay GTK.
- **Phím tắt toàn cục (`pynput`)**:
  - `pynput.keyboard.GlobalHotKeys` hoạt động native trên Windows thông qua Windows Hook (`SetWindowsHookEx`).
- **OSD Popup (`daemon/osd.py`)**:
  - `tkinter` là thư viện tiêu chuẩn kèm sẵn của Python trên Windows, các thuộc tính `-topmost`, `-alpha` và `-overrideredirect` đều tương thích 100%.

### 2.4. Khởi động ngầm không hiện cửa sổ đen (Headless) & Autostart
- **`start.vbs` (Silent Launcher)**:
  - Sử dụng Windows Scripting Host để gọi `.venv\Scripts\pythonw.exe main.py --service all`.
  - Tham số `0` đảm bảo **100% không bao giờ hiện cửa sổ đen CMD** khi chạy ngầm.
- **`start.bat` (Debug Launcher)**:
  - Dành cho việc kiểm tra log trong quá trình phát triển trên Windows.
- **`setup_windows.bat` (Cài đặt tự động & Autostart)**:
  - Tự tạo `.venv`.
  - Tự động kiểm tra lệnh `nvidia-smi`:
    - Nếu có GPU: Cài đặt bản PyTorch CUDA (`--index-url https://download.pytorch.org/whl/cu121`).
    - Nếu không có GPU: Cài đặt bản PyTorch CPU siêu nhẹ (`--index-url https://download.pytorch.org/whl/cpu`, chỉ tải ~200MB thay vì 3GB).
  - Tự động tạo shortcut `LocalASR.vbs` vào thư mục Startup của Windows (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`) để khởi động cùng máy.

---

## 3. Danh sách file thay đổi & tạo mới

| File | Hành động | Mục đích |
| :--- | :--- | :--- |
| `daemon/injector.py` | Modify | Hoàn thiện `_inject_windows` (Clipboard + Ctrl+V native). |
| `daemon/service.py` | Modify | Dùng abstraction cho BackSpace (hỗ trợ cả Windows & Linux). |
| `config.py` | Modify | Tối ưu cấu hình tự động CPU threads và device detection. |
| `asr_engine/engine.py` | Modify | Thêm logging cảnh báo chế độ CPU và tối ưu CPU float32. |
| `start.bat` | New | Script khởi động cho Windows (chế độ debug). |
| `start.vbs` | New | Script khởi động ngầm không mở CMD (chế độ production). |
| `setup_windows.bat` | New | Script 1-click cài đặt môi trường, tự chọn PyTorch CPU/CUDA và tạo autostart. |
| `README.md` | New/Modify | Hướng dẫn sử dụng trên cả 2 hệ điều hành Windows và Linux. |
