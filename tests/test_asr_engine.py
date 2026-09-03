import pytest
from unittest.mock import MagicMock
from asr_engine.engine import ASREngine

def test_asr_engine_lazy_load():
    engine = ASREngine(model_name="test_model", device="cpu", lazy_load=True)
    assert engine.is_loaded is False
    assert engine.model is None

def test_asr_engine_mock_transcribe():
    engine = ASREngine(model_name="test_model", device="cpu", lazy_load=True)
    engine._mock_transcribe = MagicMock(return_value="xin chào việt nam")
    result = engine._mock_transcribe("audio.wav")
    assert result == "xin chào việt nam"
