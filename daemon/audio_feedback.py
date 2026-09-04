import numpy as np
import sounddevice as sd
import threading
from typing import Optional

class SoundFeedback:
    """Generates and plays smooth synthetic audio cues for Voice Typing interactions."""
    def __init__(self, sample_rate: int = 16000, enabled: bool = True):
        self.sample_rate = sample_rate
        self.enabled = enabled

    def _generate_tone(self, freqs: list[float], duration: float, volume: float = 0.18) -> np.ndarray:
        """Generate smooth sine wave sequence with fade-in and fade-out to prevent clicks."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        
        # Build composite tone or chord
        wave = np.zeros(n_samples, dtype=np.float32)
        for f in freqs:
            wave += np.sin(2 * np.pi * f * t).astype(np.float32)
        wave = wave / len(freqs) * volume

        # Apply smooth cosine envelope (fade in/out)
        fade_len = min(int(self.sample_rate * 0.015), n_samples // 4)
        if fade_len > 0:
            fade_in = (1 - np.cos(np.linspace(0, np.pi, fade_len))) / 2.0
            fade_out = (1 + np.cos(np.linspace(0, np.pi, fade_len))) / 2.0
            wave[:fade_len] *= fade_in
            wave[-fade_len:] *= fade_out

        return wave

    def _play_async(self, audio: np.ndarray):
        """Play audio asynchronously without blocking the caller."""
        if not self.enabled:
            return

        def _play():
            try:
                sd.play(audio, samplerate=self.sample_rate)
                sd.wait()
            except Exception as e:
                # Do not interrupt core daemon flow if audio device is unavailable
                pass

        threading.Thread(target=_play, daemon=True).start()

    def play_start(self):
        """Crisp ascending synth chime when recording begins (523Hz -> 784Hz)."""
        if not self.enabled:
            return
        t1 = self._generate_tone([523.25], 0.065, volume=0.15) # C5
        t2 = self._generate_tone([783.99], 0.090, volume=0.18) # G5
        combined = np.concatenate([t1, t2])
        self._play_async(combined)

    def play_stop(self):
        """Warm descending chime when recording completes & processing starts (784Hz -> 523Hz)."""
        if not self.enabled:
            return
        t1 = self._generate_tone([783.99], 0.060, volume=0.16) # G5
        t2 = self._generate_tone([523.25], 0.080, volume=0.14) # C5
        combined = np.concatenate([t1, t2])
        self._play_async(combined)

    def play_cancel(self):
        """Subtle double alert tone when user cancels (ESC)."""
        if not self.enabled:
            return
        gap = np.zeros(int(self.sample_rate * 0.03), dtype=np.float32)
        t1 = self._generate_tone([349.23], 0.045, volume=0.16) # F4
        t2 = self._generate_tone([293.66], 0.060, volume=0.15) # D4
        combined = np.concatenate([t1, gap, t2])
        self._play_async(combined)
