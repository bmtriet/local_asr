import threading
import time
from typing import Optional
from PIL import Image, ImageDraw
import pystray

class TrayIndicator:
    """Manages the system tray icon with animated feedback."""
    def __init__(self, on_exit: Optional[callable] = None, on_restart: Optional[callable] = None, initial_state: str = "idle"):
        self.state = initial_state
        self.on_exit = on_exit
        self.on_restart = on_restart
        self.icon = None
        self._animating = False
        self._anim_step = 0
        self._lock = threading.Lock()

    def _create_icon_image(self, state: str, step: int = 0) -> Image.Image:
        size = (64, 64)
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        if state == "recording":
            # Pulsing red circle animation
            pulse_radius = 20 + (step % 5) * 2
            # Glow circle
            draw.ellipse([32 - pulse_radius, 32 - pulse_radius, 32 + pulse_radius, 32 + pulse_radius], fill=(239, 68, 68, 160))
            # Center bright red core
            draw.ellipse([22, 22, 42, 42], fill=(220, 38, 38, 255))
        elif state == "transcribing":
            # Yellow spinner / processing indicator
            draw.ellipse([14, 14, 50, 50], outline=(234, 179, 8, 255), width=6)
            angle = (step * 45) % 360
            draw.arc([14, 14, 50, 50], start=angle, end=angle + 90, fill=(255, 255, 255, 255), width=6)
        elif state == "loading":
            # Cyan spinner: Background model loading indicator
            draw.ellipse([14, 14, 50, 50], outline=(99, 102, 241, 160), width=5)
            angle = (step * 30) % 360
            draw.arc([14, 14, 50, 50], start=angle, end=angle + 120, fill=(56, 189, 248, 255), width=6)
        else:
            # Idle: Sleek Emerald green microphone badge (Enlarged by ~100% for clear visibility)
            draw.ellipse([4, 4, 60, 60], fill=(16, 185, 129, 255))
            # Inner white mic capsule
            draw.rounded_rectangle([25, 15, 39, 39], radius=7, fill=(255, 255, 255, 255))
            # Mic cradle arc
            draw.arc([19, 24, 45, 46], start=0, end=180, fill=(255, 255, 255, 255), width=3)
            # Mic stand stem & base
            draw.line([32, 46, 32, 53], fill=(255, 255, 255, 255), width=3)
            draw.line([25, 53, 39, 53], fill=(255, 255, 255, 255), width=3)

        return image

    def set_state(self, state: str):
        """Set indicator state: 'idle', 'recording', 'transcribing'."""
        self.state = state
        with self._lock:
            if self.icon:
                try:
                    self.icon.icon = self._create_icon_image(self.state, self._anim_step)
                    self.icon.title = f"Local ASR ({self.state.title()})"
                except Exception:
                    pass

    def _animation_loop(self):
        while self._animating:
            if self.state in ["recording", "transcribing", "loading"]:
                self._anim_step += 1
                with self._lock:
                    if self.icon:
                        try:
                            self.icon.icon = self._create_icon_image(self.state, self._anim_step)
                        except Exception:
                            pass
            time.sleep(0.12)

    def _setup_icon(self):
        self._animating = True
        anim_thread = threading.Thread(target=self._animation_loop, daemon=True)
        anim_thread.start()

        menu = pystray.Menu(
            pystray.MenuItem("Local ASR Voice Typing", lambda *args: None, enabled=False),
            pystray.MenuItem("About & GitHub", self._open_about),
            pystray.MenuItem("Open Web UI", self._open_web_ui),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Restart App", self._restart),
            pystray.MenuItem("Exit", self._stop)
        )

        self.icon = pystray.Icon(
            "LocalASR",
            icon=self._create_icon_image(self.state),
            title=f"Local ASR ({self.state.title()})",
            menu=menu
        )

    def run_in_background(self):
        """Start the system tray icon in a dedicated daemon thread."""
        self._setup_icon()
        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

    def run_blocking(self):
        """Start the system tray icon blocking the current thread (required for Linux GTK)."""
        self._setup_icon()
        self.icon.run()

    def _open_about(self, *args):
        import webbrowser
        webbrowser.open("https://github.com/bmtriet/local_asr")

    def _open_web_ui(self, *args):
        import webbrowser
        from config import get_settings
        s = get_settings()
        webbrowser.open(f"http://{s.HOST}:{s.PORT}")

    def _restart(self, *args):
        self._animating = False
        if self.icon:
            self.icon.stop()
            self.icon = None
        callback = self.on_restart
        self.on_restart = None
        if callback:
            callback()
        else:
            import sys
            import os
            import subprocess
            # Spawn fresh independent process
            subprocess.Popen([sys.executable] + sys.argv, close_fds=True)
            os._exit(0)

    def _stop(self, *args):
        self._animating = False
        if self.icon:
            self.icon.stop()
            self.icon = None
        callback = self.on_exit
        self.on_exit = None
        if callback:
            callback()
        else:
            import os
            os._exit(0)
