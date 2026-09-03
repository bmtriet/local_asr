import threading
import time
from typing import Optional
from pynput import keyboard
from config import get_settings
from storage.database import Database
from asr_engine.engine import ASREngine
from daemon.audio_recorder import AudioRecorder
from daemon.injector import TextInjector
from daemon.tray import TrayIndicator

class VoiceTypingDaemon:
    def __init__(
        self,
        engine: Optional[ASREngine] = None,
        db: Optional[Database] = None,
        show_tray: bool = True
    ):
        self.settings = get_settings()
        self.db = db or Database()
        self.db.init_db()
        self.engine = engine or ASREngine(lazy_load=True)
        self.recorder = AudioRecorder(sample_rate=self.settings.SAMPLE_RATE)
        self.injector = TextInjector()
        self.tray = TrayIndicator(on_exit=self.stop) if show_tray else None

        self.is_recording = False
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._lock = threading.Lock()

    def toggle_recording(self):
        """Toggle recording state via hotkey."""
        with self._lock:
            if not self.is_recording:
                self._start()
            else:
                self._stop_and_process()

    def _start(self):
        print("[VoiceTyping] Hotkey pressed -> Starting recording...")
        self.is_recording = True
        if self.tray:
            self.tray.set_state("recording")
        self.recorder.start_recording()

    def _stop_and_process(self):
        print("[VoiceTyping] Hotkey pressed -> Stopping recording & processing...")
        self.is_recording = False
        if self.tray:
            self.tray.set_state("transcribing")

        result = self.recorder.stop_recording()
        if not result:
            print("[VoiceTyping] Audio too short or empty.")
            if self.tray:
                self.tray.set_state("idle")
            return

        audio_path, duration = result

        # Run transcription in separate worker to keep hotkey responsive
        def worker():
            try:
                text = self.engine.transcribe(audio_path)
                if text:
                    text = text.strip()
                    text = text[0].upper() + text[1:]
                print(f"[VoiceTyping] Transcribed: '{text}' ({duration:.1f}s)")
                if text:
                    # 1. Inject into focused window
                    self.injector.inject_text(text)
                    # 2. Save into SQLite database
                    self.db.save_transcription(
                        audio_path=audio_path,
                        duration=duration,
                        raw_text=text
                    )
            except Exception as e:
                print(f"[VoiceTyping] Error during transcription/injection: {e}")
            finally:
                if self.tray:
                    self.tray.set_state("idle")

        threading.Thread(target=worker, daemon=True).start()

    def _parse_hotkey(self, hotkey_input: str) -> str:
        """Parse hotkey string for pynput GlobalHotKeys, e.g. 'ctrl+alt+space' -> '<ctrl>+<alt>+<space>'."""
        parts = hotkey_input.lower().split("+")
        formatted_parts = [f"<{p.strip()}>" if len(p.strip()) > 1 else p.strip() for p in parts]
        return "+".join(formatted_parts)

    def update_hotkey(self, new_hotkey: str):
        """Dynamically rebind hotkey without restarting service."""
        try:
            hotkey_str = self._parse_hotkey(new_hotkey)
            new_listener = keyboard.GlobalHotKeys({
                hotkey_str: self.toggle_recording
            })
            new_listener.start()
            if self._listener:
                self._listener.stop()
            self._listener = new_listener
            self.settings.HOTKEY = new_hotkey
            print(f"[VoiceTyping] Hotkey updated to: {hotkey_str}")
            return True
        except Exception as e:
            print(f"[VoiceTyping] Failed to bind hotkey {new_hotkey}: {e}")
            return False

    def start(self):
        """Start global hotkey listener and tray icon."""
        if self.tray:
            self.tray.run_in_background()

        # Check if user saved custom hotkey in DB
        db_hotkey = self.db.get_setting("hotkey")
        active_hotkey = db_hotkey or self.settings.HOTKEY
        self.settings.HOTKEY = active_hotkey

        hotkey_str = self._parse_hotkey(active_hotkey)
        print(f"[VoiceTyping] Listening for global hotkey: {hotkey_str}")
        self._listener = keyboard.GlobalHotKeys({
            hotkey_str: self.toggle_recording
        })
        self._listener.start()

    def stop(self):
        print("[VoiceTyping] Stopping daemon...")
        listener = self._listener
        self._listener = None
        if listener:
            listener.stop()
        tray = self.tray
        self.tray = None
        if tray:
            tray._stop()
