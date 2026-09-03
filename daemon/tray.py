import threading
import time
from PIL import Image, ImageDraw
import pystray

class TrayIndicator:
    """Manages the system tray icon with animated feedback."""
    def __init__(self, on_exit=None, on_restart=None):
        self.state = "idle"  # idle | recording | transcribing
        self.icon = None
        self.on_exit = on_exit
        self.on_restart = on_restart
        self._animating = False
        self._thread = None
        self._anim_step = 0

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
        else:
            # Idle: Sleek Emerald green microphone badge
            draw.ellipse([16, 16, 48, 48], fill=(16, 185, 129, 255))
            # Inner white mic shape
            draw.rounded_rectangle([28, 22, 36, 38], radius=4, fill=(255, 255, 255, 255))
            draw.arc([24, 28, 40, 42], start=0, end=180, fill=(255, 255, 255, 255), width=2)
            draw.line([32, 42, 32, 48], fill=(255, 255, 255, 255), width=2)

        return image

    def set_state(self, state: str):
        """Set indicator state: 'idle', 'recording', 'transcribing'."""
        self.state = state
        if self.icon:
            self.icon.icon = self._create_icon_image(self.state, self._anim_step)
            self.icon.title = f"Local ASR ({self.state.title()})"

    def _animation_loop(self):
        while self._animating:
            if self.state in ["recording", "transcribing"]:
                self._anim_step += 1
                if self.icon:
                    self.icon.icon = self._create_icon_image(self.state, self._anim_step)
            time.sleep(0.12)

    def _setup_icon(self):
        self._animating = True
        anim_thread = threading.Thread(target=self._animation_loop, daemon=True)
        anim_thread.start()

        menu = pystray.Menu(
            pystray.MenuItem("Local ASR Voice Typing", lambda *args: None, enabled=False),
            pystray.MenuItem("Open Web UI", self._open_web_ui),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Restart App", self._restart),
            pystray.MenuItem("Exit", self._stop)
        )

        self.icon = pystray.Icon(
            "LocalASR",
            icon=self._create_icon_image("idle"),
            title="Local ASR (Idle)",
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
            os.execv(sys.executable, [sys.executable] + sys.argv)

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
