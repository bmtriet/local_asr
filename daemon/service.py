import threading
import time
import subprocess
import os
import sys
from typing import Optional
from pynput import keyboard
from config import get_settings
from storage.database import Database
from asr_engine.engine import ASREngine
from daemon.audio_recorder import AudioRecorder
from daemon.injector import TextInjector
from daemon.tray import TrayIndicator
from asr_engine.grammar import GrammarCorrector

class VoiceTypingDaemon:
    def __init__(
        self,
        engine: Optional[ASREngine] = None,
        db: Optional[Database] = None,
        show_tray: bool = True,
        on_exit: Optional[callable] = None,
        on_restart: Optional[callable] = None
    ):
        self.settings = get_settings()
        self.db = db or Database()
        self.db.init_db()
        self.engine = engine or ASREngine(lazy_load=True)
        self.grammar = GrammarCorrector(lazy_load=True)
        self.recorder = AudioRecorder(sample_rate=self.settings.SAMPLE_RATE)
        self.injector = TextInjector()
        self._on_exit_cb = on_exit
        self._on_restart_cb = on_restart
        self.tray = TrayIndicator(on_exit=self.stop, on_restart=self.restart) if show_tray else None

        self.is_recording = False
        self.current_mode = "normal"
        self._osd_process = None
        self._mode_listener = None
        self._esc_listener = None
        
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._lock = threading.Lock()

    def toggle_recording(self):
        """Toggle recording state via hotkey."""
        with self._lock:
            if not self.is_recording:
                if self._osd_process:
                    self._cleanup_osd()
                    return
                self._wait_for_mode()
            else:
                self._stop_and_process()

    def _wait_for_mode(self):
        print("[VoiceTyping] Hotkey pressed -> Waiting for translation mode...")
        # Launch OSD
        osd_path = os.path.join(os.path.dirname(__file__), "osd.py")
        self._osd_process = subprocess.Popen([sys.executable, osd_path])
        
        # Start keyboard listener for next key
        self._mode_listener = keyboard.Listener(on_press=self._on_mode_key_press)
        self._mode_listener.start()

    def _on_mode_key_press(self, key):
        # 1. If ESC is pressed, cancel OSD and return to idle
        if key == keyboard.Key.esc:
            print("[VoiceTyping] ESC pressed -> OSD cancelled.")
            self._cleanup_osd()
            if self.tray:
                self.tray.set_state("idle")
            return False

        should_backspace = False
        try:
            if hasattr(key, 'char') and key.char:
                char = key.char.lower()
                if char == 'e':
                    self.current_mode = "english"
                    should_backspace = True
                elif char == 'z':
                    self.current_mode = "chinese"
                    should_backspace = True
                else:
                    self.current_mode = "normal"
                    should_backspace = True
            elif key == keyboard.Key.space:
                self.current_mode = "normal"
                should_backspace = True
            else:
                self.current_mode = "normal"
        except Exception:
            self.current_mode = "normal"
            
        print(f"[VoiceTyping] Mode selected: {self.current_mode}")
        self._cleanup_osd()

        # Erase the mode key (e, z, space) from active window so it is not left in text
        if should_backspace:
            try:
                time.sleep(0.06)
                subprocess.run(["xdotool", "key", "--clearmodifiers", "BackSpace"], check=False)
            except Exception as e:
                print(f"[VoiceTyping] Error removing mode key: {e}")

        self._start()
        return False # Stop the listener

    def _on_esc_press(self, key):
        if key == keyboard.Key.esc:
            print("[VoiceTyping] ESC pressed during recording -> Cancelling.")
            self.cancel_recording()
            return False

    def cancel_recording(self):
        """Cancel current recording and discard audio."""
        with self._lock:
            if self._esc_listener:
                self._esc_listener.stop()
                self._esc_listener = None
            if self._osd_process:
                self._cleanup_osd()
            if self.is_recording:
                self.is_recording = False
                self.recorder.cancel_recording()
                print("[VoiceTyping] Active recording cancelled and discarded.")
            if self.tray:
                self.tray.set_state("idle")

    def _cleanup_osd(self):
        if self._osd_process:
            self._osd_process.terminate()
            self._osd_process = None
        if self._mode_listener:
            self._mode_listener.stop()
            self._mode_listener = None

    def _start(self):
        print("[VoiceTyping] Hotkey pressed -> Starting recording...")
        self.is_recording = True
        if self.tray:
            self.tray.set_state("recording")
        self.recorder.start_recording()

        # Start ESC listener during speaking/recording to allow instant cancel
        if self._esc_listener:
            self._esc_listener.stop()
        self._esc_listener = keyboard.Listener(on_press=self._on_esc_press)
        self._esc_listener.start()

    def _stop_and_process(self):
        print("[VoiceTyping] Hotkey pressed -> Stopping recording & processing...")
        self.is_recording = False
        if self._esc_listener:
            self._esc_listener.stop()
            self._esc_listener = None
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
                    # Check if grammar correction is enabled
                    is_grammar_enabled = self.settings.GRAMMAR_CORRECTION_ENABLED
                    if str(self.db.get_setting("grammar_correction_enabled", "false")).lower() == "true":
                        is_grammar_enabled = True
                    
                    final_text = text
                    if is_grammar_enabled or self.current_mode != "normal":
                        print(f"[VoiceTyping] Applying grammar correction/translation (mode: {self.current_mode})...")
                        final_text = self.grammar.correct(text, mode=self.current_mode)
                    
                    # 1. Inject into focused window
                    self.injector.inject_text(final_text)
                    # 2. Save into SQLite database
                    self.db.save_transcription(
                        audio_path=audio_path,
                        duration=duration,
                        raw_text=text,
                        corrected_text=final_text
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

    def start(self, blocking: bool = False):
        """Start global hotkey listener and tray icon."""
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

        if self.tray:
            if blocking:
                self.tray.run_blocking()
            else:
                self.tray.run_in_background()

    def stop(self):
        print("[VoiceTyping] Stopping daemon...")
        if self._esc_listener:
            self._esc_listener.stop()
            self._esc_listener = None
        if self._osd_process:
            self._cleanup_osd()
        listener = self._listener
        self._listener = None
        if listener:
            listener.stop()
        tray = self.tray
        self.tray = None
        if tray:
            tray._stop()
        if self._on_exit_cb:
            self._on_exit_cb()
        else:
            import os
            os._exit(0)

    def restart(self):
        print("[VoiceTyping] Restarting daemon & application...")
        if self._esc_listener:
            self._esc_listener.stop()
            self._esc_listener = None
        if self._osd_process:
            self._cleanup_osd()
        listener = self._listener
        self._listener = None
        if listener:
            listener.stop()
        tray = self.tray
        self.tray = None
        if tray:
            tray._animating = False
            if tray.icon:
                tray.icon.stop()
        if self._on_restart_cb:
            self._on_restart_cb()
        else:
            import sys
            import os
            os.execv(sys.executable, [sys.executable] + sys.argv)
