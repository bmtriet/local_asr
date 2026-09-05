import numpy as np
from daemon.audio_recorder import AudioRecorder

def test_get_current_audio_snapshot_window():
    rec = AudioRecorder(sample_rate=16000)
    rec.is_recording = True
    # Simulate 5 chunks of 16,000 samples (5 seconds)
    rec._frames = [np.ones((16000, 1), dtype=np.float32) for _ in range(5)]

    # Request only last 2.0 seconds (32,000 samples)
    snapshot = rec.get_current_audio_snapshot(max_seconds=2.0)
    assert snapshot is not None
    assert len(snapshot) <= 32000
    assert len(snapshot) > 0

    # Request full snapshot (None)
    full_snapshot = rec.get_current_audio_snapshot()
    assert full_snapshot is not None
    assert len(full_snapshot) == 80000
