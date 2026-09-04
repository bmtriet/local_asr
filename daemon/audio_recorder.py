import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import uuid
import time
from pathlib import Path
from typing import Optional, Callable

class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        vad_enabled: bool = False,
        vad_silence_timeout: float = 2.0,
        vad_threshold: float = 0.015,
        vad_min_speech: float = 0.3,
        on_silence_detected: Optional[Callable[[], None]] = None
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self._frames = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

        # VAD settings
        self.vad_enabled = vad_enabled
        self.vad_silence_timeout = vad_silence_timeout
        self.vad_threshold = vad_threshold
        self.vad_min_speech = vad_min_speech
        self.on_silence_detected = on_silence_detected
        
        # Audio metrics & VAD state
        self.current_rms = 0.0
        self._has_speech = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._silence_triggered = False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio callback status: {status}")
        with self._lock:
            if not self.is_recording:
                return
            self._frames.append(indata.copy())

        # Measure audio energy (RMS)
        try:
            rms = float(np.sqrt(np.mean(indata**2)))
            self.current_rms = self.current_rms * 0.7 + rms * 0.3
        except Exception:
            rms = 0.0

        # Silence VAD logic
        if self.vad_enabled and not self._silence_triggered:
            now = time.time()
            if rms > self.vad_threshold:
                if not self._has_speech:
                    self._has_speech = True
                    self._speech_start_time = now
                self._last_speech_time = now
            elif self._has_speech:
                # If speech was present and lasted at least vad_min_speech, check silence gap
                speech_duration = (self._last_speech_time - self._speech_start_time)
                silence_gap = now - self._last_speech_time
                # Speech must have lasted at least vad_min_speech (or speech was registered)
                if silence_gap >= self.vad_silence_timeout:
                    self._silence_triggered = True
                    if self.on_silence_detected:
                        threading.Thread(target=self.on_silence_detected, daemon=True).start()

    def start_recording(self):
        """Begin audio capture stream from default mic."""
        with self._lock:
            self._frames = []
            self.is_recording = True
            self.current_rms = 0.0
            self._has_speech = False
            self._speech_start_time = 0.0
            self._last_speech_time = 0.0
            self._silence_triggered = False

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._audio_callback
            )
            self._stream.start()

    def stop_recording(self, output_dir: Optional[Path] = None) -> Optional[tuple[str, float]]:
        """Stop capture, save to WAV file, and return (wav_path, duration_seconds)."""
        with self._lock:
            if not self.is_recording:
                return None
            self.is_recording = False
            stream = self._stream
            self._stream = None

        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

        with self._lock:
            if not self._frames:
                return None
            audio_data = np.concatenate(self._frames, axis=0)

        duration = float(len(audio_data)) / self.sample_rate
        if duration < 0.3:  # Too short to be speech
            return None

        if output_dir is None:
            from config import get_settings
            output_dir = get_settings().RECORDINGS_DIR

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(output_dir / f"{uuid.uuid4().hex}.wav")

        sf.write(file_path, audio_data, self.sample_rate)
        return file_path, duration

    def cancel_recording(self):
        """Stop capture and discard recorded audio frames without saving to file."""
        with self._lock:
            self.is_recording = False
            self._frames = []
            stream = self._stream
            self._stream = None

        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
