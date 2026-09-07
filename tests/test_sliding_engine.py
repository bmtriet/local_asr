import numpy as np
import pytest
from unittest.mock import MagicMock
from asr_engine.engine import ASREngine

def test_transcribe_sliding_chunk_bounds():
    engine = ASREngine(lazy_load=True)
    engine.provider = "local"
    engine.load_model = MagicMock()
    engine.is_loaded = True
    engine.model = MagicMock()
    engine.model._build_text_prompt.return_value = "prompt"
    engine.model.processor.return_value.to.return_value.to.return_value = {
        "input_ids": MagicMock(shape=[1, 10])
    }
    engine.model.model.device = "cpu"
    engine.model.model.dtype = None
    mock_seq = MagicMock()
    mock_seq.sequences = MagicMock()
    engine.model.model.generate.return_value = mock_seq
    engine.model.processor.batch_decode.return_value = ["mock transcribed chunk"]

    # Generate 10 seconds of mock audio (160,000 samples at 16kHz)
    long_audio = np.zeros(160000, dtype=np.float32)
    # With max_window_sec=3.5, it should automatically trim to bounds without error
    text = engine.transcribe_sliding_chunk(long_audio, max_window_sec=3.5)
    assert text == "mock transcribed chunk"
