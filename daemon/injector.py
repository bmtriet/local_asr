import subprocess
import shutil
import platform
import time

class TextInjector:
    """Injects text into currently focused window on Linux X11, with modular design for Windows/macOS."""
    def __init__(self):
        self.os_type = platform.system()

    def inject_text(self, text: str) -> bool:
        if not text or not text.strip():
            return False

        text = text.strip()

        if self.os_type == "Linux":
            return self._inject_linux(text)
        elif self.os_type == "Darwin":
            return self._inject_macos(text)
        elif self.os_type == "Windows":
            return self._inject_windows(text)
        else:
            print(f"Unsupported OS for direct text injection: {self.os_type}")
            return False

    def _inject_linux(self, text: str) -> bool:
        """On Linux X11, copy to CLIPBOARD, simulate Ctrl+V, then restore user's original clipboard."""
        has_xclip = shutil.which("xclip") is not None
        has_xdotool = shutil.which("xdotool") is not None

        if has_xclip and has_xdotool:
            # 1. Backup original user clipboard
            original_clipboard = None
            try:
                p_get = subprocess.Popen(["xclip", "-selection", "clipboard", "-o"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                out, _ = p_get.communicate()
                if p_get.returncode == 0:
                    original_clipboard = out
            except Exception:
                original_clipboard = None

            # 2. Put recognized text onto clipboard
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            
            # 3. Send Ctrl+V using xdotool
            time.sleep(0.05)
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=False)
            
            # 4. Restore original clipboard (or clear if it was empty)
            time.sleep(0.12)
            try:
                if original_clipboard is not None:
                    p_restore = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                    p_restore.communicate(input=original_clipboard)
                else:
                    # Clear clipboard
                    p_clear = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                    p_clear.communicate(input=b"")
            except Exception:
                pass

            return True
        elif has_xdotool:
            # Fallback: type directly using xdotool (does not touch clipboard at all)
            subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", text], check=False)
            return True
        else:
            # Simulation / fallback
            subprocess.run(["echo", text], check=False)
            return True

    def _inject_macos(self, text: str) -> bool:
        """macOS pbcopy + AppleScript Keystroke paste, then restore original pbpaste."""
        original_clipboard = None
        try:
            # 1. Backup original clipboard
            p_get = subprocess.Popen(["pbpaste"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = p_get.communicate()
            if p_get.returncode == 0:
                original_clipboard = out
        except Exception:
            original_clipboard = None

        try:
            # 2. Copy recognized text
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            
            # 3. Paste
            time.sleep(0.05)
            subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'])
            
            # 4. Restore original clipboard
            time.sleep(0.12)
            if original_clipboard is not None:
                p_restore = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p_restore.communicate(input=original_clipboard)
            else:
                p_clear = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p_clear.communicate(input=b"")
            return True
        except Exception as e:
            print("macOS injection error:", e)
            return False

    def _inject_windows(self, text: str) -> bool:
        """Windows clipboard paste via Win32 API and simulated Ctrl+V, then restore original clipboard."""
        try:
            import ctypes
            import time

            # Win32 Clipboard constants
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            def get_clipboard_text():
                for _ in range(5):
                    if user32.OpenClipboard(None):
                        try:
                            h_clip = user32.GetClipboardData(CF_UNICODETEXT)
                            if h_clip:
                                p_data = kernel32.GlobalLock(h_clip)
                                if p_data:
                                    text_val = ctypes.wstring_at(p_data)
                                    kernel32.GlobalUnlock(h_clip)
                                    return text_val
                        finally:
                            user32.CloseClipboard()
                    time.sleep(0.01)
                return None

            def set_clipboard_text(val: str):
                for _ in range(10):
                    if user32.OpenClipboard(None):
                        try:
                            user32.EmptyClipboard()
                            if val:
                                data = val.encode("utf-16le") + b"\x00\x00"
                                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                                if h_mem:
                                    p_mem = kernel32.GlobalLock(h_mem)
                                    ctypes.memmove(p_mem, data, len(data))
                                    kernel32.GlobalUnlock(h_mem)
                                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                            return True
                        finally:
                            user32.CloseClipboard()
                    time.sleep(0.01)
                return False

            # 1. Backup original text in clipboard
            original_text = get_clipboard_text()

            # 2. Set new text to clipboard
            set_clipboard_text(text)

            # 3. Simulate Ctrl+V using pynput
            time.sleep(0.05)
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            with kbd.pressed(Key.ctrl):
                kbd.tap('v')

            # 4. Restore original clipboard
            time.sleep(0.12)
            set_clipboard_text(original_text or "")

            return True
        except Exception as e:
            print(f"Windows injection error: {e}")
            return False
