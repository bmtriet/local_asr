import pytest
import platform
from unittest.mock import MagicMock, patch
from config import get_settings
from daemon.injector import TextInjector
from asr_engine.engine import ASREngine

def test_cpu_mode_configuration():
    settings = get_settings()
    assert hasattr(settings, "CPU_THREADS")
    assert settings.CPU_THREADS >= 1

    # Verify ASREngine CPU initialization without GPU
    with patch("torch.cuda.is_available", return_value=False):
        engine = ASREngine(lazy_load=True)
        assert engine.device == "cpu"
        import torch
        assert engine.dtype == torch.float32

def test_injector_cross_platform():
    injector = TextInjector()
    assert injector.os_type in ["Linux", "Darwin", "Windows"]
    
    # Test empty or whitespace text
    assert injector.inject_text("") is False
    assert injector.inject_text("   ") is False

def test_service_send_backspace(tmp_path):
    from daemon.service import VoiceTypingDaemon
    from storage.database import Database
    db = Database(str(tmp_path / "test_bk.db"))
    db.init_db()

    daemon = VoiceTypingDaemon(db=db, show_tray=False)
    # Ensure _send_backspace runs without throwing exceptions
    daemon._send_backspace()
