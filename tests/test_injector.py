import pytest
from unittest.mock import patch, MagicMock
from daemon.injector import TextInjector

def test_injector_inject_via_clipboard():
    injector = TextInjector()
    with patch("subprocess.run") as mock_run:
        success = injector.inject_text("Xin chào Việt Nam")
        assert success is True
        assert mock_run.called

def test_injector_empty_text():
    injector = TextInjector()
    with patch("subprocess.run") as mock_run:
        success = injector.inject_text("")
        assert success is False
        assert not mock_run.called
