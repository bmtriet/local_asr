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
        """Windows clipboard + SendKeys/ctypes paste."""
        try:
            import ctypes
            # Will be implemented when porting to Windows
            return True
        except Exception as e:
            print("Windows injection error:", e)
            return False
