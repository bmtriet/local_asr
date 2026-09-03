import pytest
from unittest.mock import MagicMock
from training.dataset_builder import DatasetBuilder

def test_dataset_builder_collect_samples():
    db_mock = MagicMock()
    db_mock.get_samples_for_training.return_value = [
        {"id": 1, "audio_path": "audio1.wav", "corrected_text": "Xin chào"},
        {"id": 2, "audio_path": "audio2.wav", "corrected_text": "Hôm nay trời đẹp"}
    ]
    builder = DatasetBuilder(db_mock)
    samples = builder.collect_samples()
    assert len(samples) == 2
    assert samples[0]["text"] == "Xin chào"
    assert samples[1]["text"] == "Hôm nay trời đẹp"
