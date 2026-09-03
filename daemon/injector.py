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
        """On Linux X11, copy to PRIMARY & CLIPBOARD selections using xclip/xsel or xdotool simulate Ctrl+V."""
        # Using xclip / xsel if available, or xdotool directly
        has_xclip = shutil.which("xclip") is not None
        has_xdotool = shutil.which("xdotool") is not None

        if has_xclip and has_xdotool:
            # Copy to clipboard via xclip
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            
            # Send Ctrl+V using xdotool
            time.sleep(0.05)
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=False)
            return True
        elif has_xdotool:
            # Fallback: type directly using xdotool
            subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", text], check=False)
            return True
        else:
            # Simulation / fallback
            subprocess.run(["echo", text], check=False)
            return True

    def _inject_macos(self, text: str) -> bool:
        """macOS pbcopy + AppleScript Keystroke paste."""
        try:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'])
            return True
        except Exception as e:
            print("macOS injection error:", e)
            return False

    def _inject_windows(self, text: str) -> bool:
        """Windows clipboard paste via Win32 API and simulated Ctrl+V."""
        try:
            import ctypes
            import time

            # Win32 Clipboard constants
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Open clipboard with retry
            opened = False
            for _ in range(10):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.01)

            if opened:
                try:
                    user32.EmptyClipboard()
                    data = text.encode("utf-16le") + b"\x00\x00"
                    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                    if h_mem:
                        p_mem = kernel32.GlobalLock(h_mem)
                        ctypes.memmove(p_mem, data, len(data))
                        kernel32.GlobalUnlock(h_mem)
                        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                finally:
                    user32.CloseClipboard()

            # Simulate Ctrl+V using pynput
            time.sleep(0.05)
            from pynput.keyboard import Controller, Key
            kbd = Controller()
            with kbd.pressed(Key.ctrl):
                kbd.tap('v')
            return True
        except Exception as e:
            print(f"Windows injection error: {e}")
            return False
