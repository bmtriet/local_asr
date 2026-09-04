import pytest
import numpy as np
from unittest.mock import MagicMock
from daemon.audio_feedback import SoundFeedback
from daemon.audio_recorder import AudioRecorder
from storage.database import Database
from daemon.service import VoiceTypingDaemon

def test_sound_feedback_tones():
    feedback = SoundFeedback(sample_rate=16000, enabled=True)
    
    # Test tone generation returns non-empty float32 waveform
    tone = feedback._generate_tone([523.25], 0.05, volume=0.2)
    assert isinstance(tone, np.ndarray)
    assert tone.dtype == np.float32
    assert len(tone) == int(16000 * 0.05)
    assert np.max(np.abs(tone)) <= 0.25

    # Test playback does not raise errors when disabled
    feedback.enabled = False
    feedback.play_start()
    feedback.play_stop()
    feedback.play_cancel()

def test_audio_recorder_vad_and_rms():
    silence_calls = []
    def on_silence():
        silence_calls.append(True)

    recorder = AudioRecorder(
        sample_rate=16000,
        vad_enabled=True,
        vad_silence_timeout=0.03,
        vad_threshold=0.01,
        vad_min_speech=0.02,
        on_silence_detected=on_silence
    )
    recorder.is_recording = True
    
    # Simulate speech frame (high energy)
    speech_frame = np.full((1600, 1), 0.1, dtype=np.float32)
    recorder._audio_callback(speech_frame, 1600, None, None)
    assert recorder.current_rms > 0.02
    assert recorder._has_speech is True

    # Simulate quiet frame after speech with sleep > vad_silence_timeout
    import time
    time.sleep(0.04)
    quiet_frame = np.full((1600, 1), 0.0001, dtype=np.float32)
    recorder._audio_callback(quiet_frame, 1600, None, None)
    
    time.sleep(0.05)
    assert len(silence_calls) >= 1

def test_ux_settings_persistence(tmp_path):
    db_path = str(tmp_path / "test_ux.db")
    db = Database(db_path)
    db.init_db()

    # Default check
    assert db.get_setting("sound_cues_enabled") is None
    
    # Set and get
    db.set_setting("sound_cues_enabled", "true")
    db.set_setting("hotkey_mode", "hold")
    db.set_setting("vad_enabled", "true")
    db.set_setting("vad_silence_timeout", "2.5")

    assert db.get_setting("sound_cues_enabled") == "true"
    assert db.get_setting("hotkey_mode") == "hold"
    assert db.get_setting("vad_enabled") == "true"
    assert db.get_setting("vad_silence_timeout") == "2.5"

def test_daemon_sound_and_mode_integration(tmp_path):
    db = Database(str(tmp_path / "daemon_ux.db"))
    db.init_db()

    daemon = VoiceTypingDaemon(db=db, show_tray=False)
    daemon.sound_feedback = MagicMock()
    daemon.recorder = MagicMock()
    daemon.recorder.stop_recording.return_value = ("/tmp/mock.wav", 1.2)

    # 1. Test start plays chime
    daemon._start_recording_and_osd()
    assert daemon.is_recording is True
    assert daemon.sound_feedback.play_start.called

    # 2. Test cancel plays cancel cue
    daemon.cancel_recording()
    assert daemon.is_recording is False
    assert daemon.sound_feedback.play_cancel.called

    # 3. Test stop plays stop cue
    daemon.is_recording = True
    daemon._stop_and_process()
    assert daemon.is_recording is False
    assert daemon.sound_feedback.play_stop.called

def test_daemon_hold_to_talk_press_and_release(tmp_path):
    db = Database(str(tmp_path / "daemon_hold.db"))
    db.init_db()
    db.set_setting("hotkey_mode", "hold")

    daemon = VoiceTypingDaemon(db=db, show_tray=False)
    daemon.sound_feedback = MagicMock()
    daemon.recorder = MagicMock()
    daemon.recorder.stop_recording.return_value = ("/tmp/mock.wav", 1.0)

    # When hotkey pressed in hold mode -> starts recording
    daemon._on_hotkey_press()
    assert daemon.is_recording is True

    # When hotkey released in hold mode -> stops recording and processes
    daemon._on_hotkey_release()
    assert daemon.is_recording is False
    assert daemon.recorder.stop_recording.called
