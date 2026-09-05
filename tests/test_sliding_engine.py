import numpy as np
import pytest
from asr_engine.engine import ASREngine

def test_transcribe_sliding_chunk_bounds():
    engine = ASREngine(lazy_load=True)
    # Generate 10 seconds of mock audio (160,000 samples at 16kHz)
    long_audio = np.zeros(160000, dtype=np.float32)
    # With max_window_sec=3.5, it should automatically trim to bounds without error
    text = engine.transcribe_sliding_chunk(long_audio, max_window_sec=3.5)
    assert isinstance(text, str)
