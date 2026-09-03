import pytest
from daemon.tray import TrayIndicator
from daemon.service import VoiceTypingDaemon

def test_tray_indicator_callbacks():
    exit_called = []
    restart_called = []

    def mock_exit():
        exit_called.append(True)

    def mock_restart():
        restart_called.append(True)

    tray = TrayIndicator(on_exit=mock_exit, on_restart=mock_restart)
    assert tray.state == "idle"
    
    # Test restart trigger
    tray._restart()
    assert len(restart_called) == 1

    # Test exit trigger
    tray2 = TrayIndicator(on_exit=mock_exit, on_restart=mock_restart)
    tray2._stop()
    assert len(exit_called) == 1

def test_daemon_lifecycle_callbacks(tmp_path):
    from storage.database import Database
    db = Database(str(tmp_path / "test_life.db"))
    db.init_db()

    exit_called = []
    restart_called = []

    daemon = VoiceTypingDaemon(
        db=db,
        show_tray=False,
        on_exit=lambda: exit_called.append(True),
        on_restart=lambda: restart_called.append(True)
    )

    daemon.restart()
    assert len(restart_called) == 1

    daemon.stop()
    assert len(exit_called) == 1

def test_daemon_esc_cancel(tmp_path):
    from pynput import keyboard
    from storage.database import Database
    db = Database(str(tmp_path / "test_esc.db"))
    db.init_db()

    daemon = VoiceTypingDaemon(db=db, show_tray=False)
    
    # 1. Test ESC cancels OSD
    from unittest.mock import MagicMock
    mock_proc = MagicMock()
    daemon._osd_process = mock_proc
    ret = daemon._on_mode_key_press(keyboard.Key.esc)
    assert ret is False
    assert daemon._osd_process is None
    assert mock_proc.terminate.called
    assert daemon.is_recording is False

    # 2. Test ESC cancels active recording
    daemon.is_recording = True
    daemon.cancel_recording()
    assert daemon.is_recording is False

def test_daemon_mode_timeout(tmp_path):
    from unittest.mock import MagicMock
    from storage.database import Database
    db = Database(str(tmp_path / "test_timeout.db"))
    db.init_db()

    daemon = VoiceTypingDaemon(db=db, show_tray=False)
    mock_proc = MagicMock()
    daemon.recorder = MagicMock()

    # Hotkey pressed: starts recording immediately and opens OSD
    daemon._start_recording_and_osd()
    assert daemon.is_recording is True
    assert daemon.recorder.start_recording.called

    # Mock osd process
    daemon._osd_process = mock_proc

    # Trigger timeout handler: OSD closes, recording continues
    daemon._on_mode_timeout()

    assert daemon.current_mode == "normal"
    assert daemon._osd_process is None
    assert mock_proc.terminate.called
    assert daemon.is_recording is True

    # User presses mode key while speaking: mode updates, recording continues
    daemon._osd_process = MagicMock()
    daemon._on_mode_key_press(MagicMock(char='e'))
    assert daemon.current_mode == "english"
    assert daemon.is_recording is True
