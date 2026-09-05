import threading
import time
import subprocess
import os
import sys
import platform
import shutil
from typing import Optional
from pynput import keyboard
from config import get_settings
from storage.database import Database
from asr_engine.engine import ASREngine
from daemon.audio_recorder import AudioRecorder
from daemon.injector import TextInjector
from daemon.tray import TrayIndicator
from asr_engine.grammar import GrammarCorrector
from daemon.audio_feedback import SoundFeedback

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
        
        # Load ASR provider config from DB
        asr_provider = self.db.get_setting("asr_provider", getattr(self.settings, "ASR_PROVIDER", "local"))
        asr_endpoint = self.db.get_setting("asr_api_endpoint", getattr(self.settings, "ASR_API_ENDPOINT", "http://127.0.0.1:8000/v1/audio/transcriptions"))
        asr_key = self.db.get_setting("asr_api_key", getattr(self.settings, "ASR_API_KEY", ""))
        self.engine.set_config(provider=asr_provider, api_endpoint=asr_endpoint, api_key=asr_key)

        qwen_saved = self.db.get_setting("qwen25_enabled", str(getattr(self.settings, "QWEN25_ENABLED", True)))
        self.qwen25_enabled = (qwen_saved.lower() == "true")
        self.grammar = GrammarCorrector(lazy_load=True)
        
        # Load Translation provider config from DB
        trans_provider = self.db.get_setting("translation_provider", getattr(self.settings, "TRANSLATION_PROVIDER", "local"))
        trans_url = self.db.get_setting("translation_api_base_url", getattr(self.settings, "TRANSLATION_API_BASE_URL", "http://localhost:11434/v1"))
        trans_key = self.db.get_setting("translation_api_key", getattr(self.settings, "TRANSLATION_API_KEY", "ollama"))
        trans_model = self.db.get_setting("translation_model_name", getattr(self.settings, "TRANSLATION_MODEL_NAME", "qwen2.5:0.5b"))
        self.grammar.set_config(provider=trans_provider, api_base_url=trans_url, api_key=trans_key, api_model=trans_model)

        # Load UX settings from DB
        cues_enabled = (self.db.get_setting("sound_cues_enabled", "true").lower() == "true")
        self.sound_feedback = SoundFeedback(sample_rate=self.settings.SAMPLE_RATE, enabled=cues_enabled)

        vad_enabled = (self.db.get_setting("vad_enabled", "false").lower() == "true")
        vad_timeout = float(self.db.get_setting("vad_silence_timeout", "2.0") or 2.0)
        self.hotkey_mode = self.db.get_setting("hotkey_mode", "toggle").lower() # "toggle" or "hold"

        self.recorder = AudioRecorder(
            sample_rate=self.settings.SAMPLE_RATE,
            vad_enabled=vad_enabled,
            vad_silence_timeout=vad_timeout,
            on_silence_detected=self._on_vad_silence
        )
        self.injector = TextInjector()
        from asr_engine.normalizer import VietnameseNormalizer
        self.normalizer = VietnameseNormalizer(db=self.db)
        self._on_exit_cb = on_exit
        self._on_restart_cb = on_restart
        initial_tray_state = "idle" if (self.engine and self.engine.is_loaded) else "loading"
        self.tray = TrayIndicator(on_exit=self.stop, on_restart=self.restart, initial_state=initial_tray_state) if show_tray else None

        # If engine is not yet loaded, warm it up in background worker without blocking startup
        if self.engine and not self.engine.is_loaded:
            self._start_background_model_preload()

        self.is_recording = False
        self.current_mode = "normal"
        self._osd_process = None
        self._mode_listener = None
        self._mode_timer = None
        self._esc_listener = None
        self._streaming_thread = None
        self._stop_streaming = threading.Event()
        
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._lock = threading.Lock()

    def _start_background_model_preload(self):
        """Asynchronously load the ASR engine in a worker thread to keep initial startup instantaneous."""
        def preload_worker():
            try:
                print("[VoiceTyping] Background model preloading started...")
                self.engine.load_model()
                print("[VoiceTyping] Background model preloading complete.")
            except Exception as e:
                print(f"[VoiceTyping] Error during background model preloading: {e}")
            finally:
                # If daemon is still idle, transition tray state from loading to idle
                if self.tray and self.tray.state == "loading":
                    self.tray.set_state("idle")

        preload_thread = threading.Thread(target=preload_worker, daemon=True)
        preload_thread.start()

    def _on_vad_silence(self):
        """Called automatically when Silence VAD detects end of speech."""
        with self._lock:
            if self.is_recording:
                print("[VoiceTyping] VAD silence detected -> Auto-stopping and transcribing...")
                self._stop_and_process()

    def toggle_recording(self):
        """Toggle recording state via hotkey."""
        with self._lock:
            if not self.is_recording:
                self._start_recording_and_osd()
            else:
                self._stop_and_process()

    def _start_recording_and_osd(self):
        print("[VoiceTyping] Hotkey pressed -> Starting recording immediately...")
        # 1. Reset mode and mark recording active immediately
        self.current_mode = "normal"
        self.is_recording = True
        if self.tray:
            self.tray.set_state("recording")
        
        # 2. Play start chime & begin audio capture without delay
        if hasattr(self, "sound_feedback") and self.sound_feedback:
            self.sound_feedback.play_start()
        self.recorder.start_recording()

        # 3. Start ESC listener during speaking/recording to allow instant cancel
        if self._esc_listener:
            self._esc_listener.stop()
        self._esc_listener = keyboard.Listener(on_press=self._on_esc_press)
        self._esc_listener.start()

        # 4. Launch OSD concurrently for optional mode selection
        osd_path = os.path.join(os.path.dirname(__file__), "osd.py")
        
        # Read user-configured OSD display settings
        osd_position = self.db.get_setting("osd_position", "top-left")
        osd_duration_str = self.db.get_setting("osd_duration", "2.0")
        try:
            osd_duration = max(0.5, float(osd_duration_str))
        except Exception:
            osd_duration = 2.0
        osd_always_on = (self.db.get_setting("osd_always_on", "false").lower() == "true")

        osd_cmd = [
            sys.executable, osd_path,
            "--position", osd_position,
            "--duration", str(osd_duration),
            "--mode", self.current_mode
        ]
        if osd_always_on or self.hotkey_mode == "hold":
            osd_cmd.append("--always-on")

        self._osd_process = subprocess.Popen(
            osd_cmd,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # 5. Start keyboard listener for mode selection keys (e, z, space)
        if self._mode_listener:
            self._mode_listener.stop()
        self._mode_listener = keyboard.Listener(on_press=self._on_mode_key_press)
        self._mode_listener.start()

        # 6. Auto-dismiss OSD after duration (if not always_on and not hold mode)
        if self._mode_timer:
            self._mode_timer.cancel()
            self._mode_timer = None

        if not osd_always_on and self.hotkey_mode != "hold":
            self._mode_timer = threading.Timer(osd_duration, self._on_mode_timeout)
            self._mode_timer.daemon = True
            self._mode_timer.start()

        # 7. Start real-time live streaming worker if enabled
        self._start_live_streaming_worker()

    def _start_live_streaming_worker(self):
        streaming_enabled_str = self.db.get_setting("streaming_transcription_enabled", str(self.settings.STREAMING_TRANSCRIPTION_ENABLED)).lower()
        if streaming_enabled_str != "true":
            return

        self._stop_streaming.clear()

        def stream_worker():
            last_text = ""
            # Wait briefly for initial speech buffer
            time.sleep(0.4)
            while not self._stop_streaming.is_set() and self.is_recording:
                try:
                    # Bounded trailing 3.5s window avoids growing memory and quadratic attention latency
                    snapshot = self.recorder.get_current_audio_snapshot(max_seconds=3.5)
                    if snapshot is not None and len(snapshot) >= int(self.settings.SAMPLE_RATE * 0.4):
                        # Bounded low-latency sliding chunk decode (always <= 300ms)
                        partial = self.engine.transcribe_sliding_chunk(
                            snapshot,
                            sample_rate=self.settings.SAMPLE_RATE,
                            max_window_sec=3.5
                        )
                        if partial and partial != last_text:
                            last_text = partial
                            # Pipe partial text to OSD
                            if self._osd_process and self._osd_process.poll() is None:
                                try:
                                    self._osd_process.stdin.write(f"text:{partial}\n")
                                    self._osd_process.stdin.flush()
                                except Exception:
                                    pass
                except Exception as e:
                    print(f"[VoiceTyping] Streaming worker error: {e}")
                
                # Check interval ~ 0.4s
                time.sleep(0.4)

        self._streaming_thread = threading.Thread(target=stream_worker, daemon=True)
        self._streaming_thread.start()

    def _stop_live_streaming_worker(self):
        self._stop_streaming.set()
        self._streaming_thread = None

    def _on_mode_timeout(self):
        with self._lock:
            if self._osd_process:
                print("[VoiceTyping] OSD timeout -> Dismissing OSD, recording continues.")
                self._cleanup_osd()

    def _on_mode_key_press(self, key):
        # 1. If ESC is pressed, cancel recording completely and return to idle
        if key == keyboard.Key.esc:
            print("[VoiceTyping] ESC pressed -> Recording cancelled.")
            self.cancel_recording()
            return False

        should_backspace = False
        selected_mode = None
        try:
            if hasattr(key, 'char') and key.char:
                char = key.char.lower()
                if char == 'e':
                    selected_mode = "english"
                    should_backspace = True
                elif char == 'z':
                    selected_mode = "chinese"
                    should_backspace = True
                elif char == 's':
                    selected_mode = "summarize"
                    should_backspace = True
                elif char == ' ':
                    selected_mode = "normal"
                    should_backspace = True
            elif key == keyboard.Key.space:
                selected_mode = "normal"
                should_backspace = True
        except Exception:
            pass

        if selected_mode:
            self.current_mode = selected_mode
            print(f"[VoiceTyping] Mode selected: {self.current_mode} (recording continues...)")

            # Update OSD dynamically via stdin so the button gets highlighted while speaking
            if self._osd_process and self._osd_process.poll() is None:
                try:
                    self._osd_process.stdin.write(f"{selected_mode}\n")
                    self._osd_process.stdin.flush()
                except Exception as e:
                    print(f"[VoiceTyping] Error updating OSD mode: {e}")

            # If in toggle mode and not always_on, schedule OSD close after brief display
            if self.hotkey_mode == "toggle":
                osd_always_on = (self.db.get_setting("osd_always_on", "false").lower() == "true")
                if not osd_always_on:
                    if self._mode_timer:
                        self._mode_timer.cancel()
                    self._mode_timer = threading.Timer(1.2, self._on_mode_timeout)
                    self._mode_timer.daemon = True
                    self._mode_timer.start()

            if should_backspace:
                self._send_backspace()
            return False

    def _send_backspace(self):
        """Cross-platform backspace tap to erase mode selection key from focused window."""
        try:
            time.sleep(0.06)
            if platform.system() == "Linux" and shutil.which("xdotool"):
                subprocess.run(["xdotool", "key", "--clearmodifiers", "BackSpace"], check=False)
            else:
                from pynput.keyboard import Controller, Key
                Controller().tap(Key.backspace)
        except Exception as e:
            print(f"[VoiceTyping] Error removing mode key: {e}")

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
                self._stop_live_streaming_worker()
                self.recorder.cancel_recording()
                if hasattr(self, "sound_feedback") and self.sound_feedback:
                    self.sound_feedback.play_cancel()
                print("[VoiceTyping] Active recording cancelled and discarded.")
            if self.tray:
                self.tray.set_state("idle")

    def _cleanup_osd(self):
        if self._mode_timer:
            self._mode_timer.cancel()
            self._mode_timer = None
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
        if hasattr(self, "sound_feedback") and self.sound_feedback:
            self.sound_feedback.play_start()
        self.recorder.start_recording()

        # Start ESC listener during speaking/recording to allow instant cancel
        if self._esc_listener:
            self._esc_listener.stop()
        self._esc_listener = keyboard.Listener(on_press=self._on_esc_press)
        self._esc_listener.start()

    def _stop_and_process(self):
        print("[VoiceTyping] Hotkey pressed -> Stopping recording & processing...")
        self.is_recording = False
        self._stop_live_streaming_worker()
        self._cleanup_osd()
        if self._esc_listener:
            self._esc_listener.stop()
            self._esc_listener = None
        if self.tray:
            self.tray.set_state("transcribing")

        if hasattr(self, "sound_feedback") and self.sound_feedback:
            self.sound_feedback.play_stop()

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
                # Retrieve user reviewed vocabulary & keywords + custom vocabulary.json for instant adaptation
                user_vocab = self.db.get_reviewed_vocabulary()
                vocab_ctx = ""
                if self.normalizer and getattr(self.normalizer, "vocab_mgr", None):
                    vocab_ctx = self.normalizer.vocab_mgr.get_context_string()
                
                combined_context = ", ".join(filter(None, [vocab_ctx, user_vocab]))
                if combined_context:
                    print(f"[VoiceTyping] Applying vocabulary context: {combined_context}")

                text = self.engine.transcribe(audio_path, context=combined_context)
                if text:
                    # Apply ITN / digit sequence normalization immediately
                    text = self.normalizer.normalize(text)
                    text = text.strip()
                    if text:
                        text = text[0].upper() + text[1:]
                print(f"[VoiceTyping] Transcribed: '{text}' ({duration:.1f}s)")
                if text:
                    # Determine active translation/grammar mode
                    default_mode = self.db.get_setting("translation_mode", "normal")
                    active_mode = self.current_mode if self.current_mode != "normal" else default_mode

                    # Check if Qwen2.5 model is enabled
                    qwen_enabled = getattr(self, "qwen25_enabled", True)
                    # Also re-sync with DB in case changed via web
                    qwen_db_val = self.db.get_setting("qwen25_enabled")
                    if qwen_db_val is not None:
                        qwen_enabled = (qwen_db_val.lower() == "true")
                        self.qwen25_enabled = qwen_enabled

                    # Check if grammar correction is enabled
                    is_grammar_enabled = self.settings.GRAMMAR_CORRECTION_ENABLED
                    if str(self.db.get_setting("grammar_correction_enabled", "false")).lower() == "true":
                        is_grammar_enabled = True
                    
                    final_text = text
                    if qwen_enabled and (is_grammar_enabled or active_mode != "normal"):
                        print(f"[VoiceTyping] Applying grammar correction/translation (mode: {active_mode})...")
                        translated = self.grammar.correct(text, mode=active_mode, custom_vocab=user_vocab)
                        if active_mode == "normal":
                            translated = self.normalizer.normalize(translated)
                        
                        # Check "add origin phrase" setting only for translation modes (english/chinese)
                        if active_mode in ["english", "chinese"]:
                            add_origin = self.settings.ADD_ORIGIN_PHRASE
                            if str(self.db.get_setting("add_origin_phrase", "false")).lower() == "true":
                                add_origin = True
                            
                            if add_origin:
                                final_text = f"{text}\n{translated}"
                            else:
                                final_text = translated
                        else:
                            final_text = translated
                    elif not qwen_enabled and active_mode != "normal":
                        print(f"[VoiceTyping] Qwen2.5 is disabled. Skipping translation ({active_mode}) and using pure transcribed text.")
                    
                    # 1. Inject into focused window
                    self.injector.inject_text(final_text)
                    # 2. Save into SQLite database (keep only source spoken text for LoRA training)
                    stored_corrected_text = text if active_mode != "normal" else final_text
                    self.db.save_transcription(
                        audio_path=audio_path,
                        duration=duration,
                        raw_text=text,
                        corrected_text=stored_corrected_text
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

    def _on_hotkey_press(self):
        """Called when hotkey combo is activated."""
        with self._lock:
            if not self.is_recording:
                self._start_recording_and_osd()
            elif self.hotkey_mode == "toggle":
                self._stop_and_process()

    def _on_hotkey_release(self):
        """Called when hotkey is released in hold-to-talk mode."""
        if self.hotkey_mode == "hold":
            with self._lock:
                if self.is_recording:
                    print("[VoiceTyping] Hotkey released (Hold mode) -> Stopping recording...")
                    self._stop_and_process()

    def _setup_hotkey_listener(self, hotkey_str: str):
        """Build and return a keyboard.Listener that tracks press & release transitions for both toggle and hold modes."""
        combo_keys = keyboard.HotKey.parse(hotkey_str)
        combo = keyboard.HotKey(combo_keys, on_activate=lambda: None)

        def on_press(key):
            try:
                canon = listener.canonical(key)
                was_active = (combo._keys <= combo._state)
                combo.press(canon)
                is_active = (combo._keys <= combo._state)
                if not was_active and is_active:
                    self._on_hotkey_press()
            except Exception:
                pass

        def on_release(key):
            try:
                canon = listener.canonical(key)
                was_active = (combo._keys <= combo._state)
                combo.release(canon)
                is_active = (combo._keys <= combo._state)
                if was_active and not is_active:
                    self._on_hotkey_release()
            except Exception:
                pass

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        return listener

    def update_hotkey(self, new_hotkey: str):
        """Dynamically rebind hotkey without restarting service."""
        try:
            hotkey_str = self._parse_hotkey(new_hotkey)
            new_listener = self._setup_hotkey_listener(hotkey_str)
            new_listener.start()
            if self._listener:
                self._listener.stop()
            self._listener = new_listener
            self.settings.HOTKEY = new_hotkey
            print(f"[VoiceTyping] Hotkey updated to: {hotkey_str} (Mode: {self.hotkey_mode})")
            return True
        except Exception as e:
            print(f"[VoiceTyping] Failed to bind hotkey {new_hotkey}: {e}")
            return False

    def update_ux_settings(self, sound_cues: Optional[bool] = None, hotkey_mode: Optional[str] = None, vad_enabled: Optional[bool] = None, vad_timeout: Optional[float] = None):
        """Update live UX settings on the active daemon instance."""
        if sound_cues is not None and hasattr(self, "sound_feedback"):
            self.sound_feedback.enabled = sound_cues
        if hotkey_mode is not None:
            self.hotkey_mode = hotkey_mode.lower()
            print(f"[VoiceTyping] Hotkey mode updated to: {self.hotkey_mode}")
        if hasattr(self, "recorder") and self.recorder:
            if vad_enabled is not None:
                self.recorder.vad_enabled = vad_enabled
            if vad_timeout is not None:
                self.recorder.vad_silence_timeout = vad_timeout

    def set_qwen25_enabled(self, enabled: bool):
        """Dynamically enable or disable Qwen2.5 loading and unload model if disabled."""
        self.qwen25_enabled = bool(enabled)
        if not self.qwen25_enabled and hasattr(self, "grammar") and self.grammar:
            self.grammar.unload_model()
            print("[VoiceTyping] Qwen2.5 disabled and model unloaded from memory.")
        else:
            print(f"[VoiceTyping] Qwen2.5 enabled state set to: {self.qwen25_enabled}")

    def update_provider_settings(
        self,
        asr_provider: Optional[str] = None,
        asr_endpoint: Optional[str] = None,
        asr_key: Optional[str] = None,
        translation_provider: Optional[str] = None,
        translation_url: Optional[str] = None,
        translation_key: Optional[str] = None,
        translation_model: Optional[str] = None,
    ):
        """Update active engine and translation provider configs at runtime."""
        if hasattr(self, "engine") and self.engine:
            self.engine.set_config(
                provider=asr_provider or self.engine.provider,
                api_endpoint=asr_endpoint or self.engine.api_endpoint,
                api_key=asr_key if asr_key is not None else self.engine.api_key
            )
        if hasattr(self, "grammar") and self.grammar:
            self.grammar.set_config(
                provider=translation_provider or self.grammar.provider,
                api_base_url=translation_url or self.grammar.api_base_url,
                api_key=translation_key if translation_key is not None else self.grammar.api_key,
                api_model=translation_model or self.grammar.api_model
            )

    def start(self, blocking: bool = False):
        """Start global hotkey listener and tray icon."""
        # Check if user saved custom hotkey in DB
        db_hotkey = self.db.get_setting("hotkey")
        active_hotkey = db_hotkey or self.settings.HOTKEY
        self.settings.HOTKEY = active_hotkey

        # Re-read active hotkey_mode from DB if present
        saved_mode = self.db.get_setting("hotkey_mode")
        if saved_mode:
            self.hotkey_mode = saved_mode.lower()

        hotkey_str = self._parse_hotkey(active_hotkey)
        print(f"[VoiceTyping] Listening for global hotkey: {hotkey_str} (Mode: {self.hotkey_mode})")
        self._listener = self._setup_hotkey_listener(hotkey_str)
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
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv, close_fds=True)
            os._exit(0)

    def switch_profile(self, profile_id: str):
        """Switch active profile in daemon, loading profile-specific vocabulary and LoRA adapter."""
        clean_id = profile_id.strip().lower() or "default"
        print(f"[VoiceTyping] Switching daemon to profile '{clean_id}'...")
        if self.normalizer and getattr(self.normalizer, "vocab_mgr", None):
            self.normalizer.vocab_mgr.switch_profile(clean_id)
        if self.engine:
            self.engine.switch_profile_adapter(clean_id)
        print(f"[VoiceTyping] Successfully switched daemon to profile '{clean_id}'")
