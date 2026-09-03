import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import uuid
from pathlib import Path
from typing import Optional

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self._frames = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio callback status: {status}")
        with self._lock:
            if self.is_recording:
                self._frames.append(indata.copy())

    def start_recording(self):
        """Begin audio capture stream from default mic."""
        with self._lock:
            self._frames = []
            self.is_recording = True
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
            stream.stop()
            stream.close()

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
