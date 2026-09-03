import os
import pytest
from storage.database import Database

@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test.db")
    database = Database(db_path=db_file)
    database.init_db()
    return database

def test_transcription_lifecycle(db):
    row_id = db.save_transcription("audio/test.wav", 2.5, "xin chào thế giới")
    assert row_id > 0
    
    items = db.get_transcriptions()
    assert len(items) == 1
    assert items[0]["raw_text"] == "xin chào thế giới"
    assert items[0]["corrected_text"] == "xin chào thế giới"
    assert items[0]["is_reviewed"] == 0

    success = db.update_correction(row_id, "Xin chào Thế Giới")
    assert success is True
    
    items = db.get_transcriptions()
    assert items[0]["corrected_text"] == "Xin chào Thế Giới"
    assert items[0]["is_reviewed"] == 1

    training_samples = db.get_samples_for_training()
    assert len(training_samples) == 1
    assert training_samples[0]["id"] == row_id
    assert training_samples[0]["corrected_text"] == "Xin chào Thế Giới"

    # Mark as trained
    mark_success = db.mark_samples_trained([row_id])
    assert mark_success is True

    # After marked as trained, it should not appear in new training batch
    training_samples_after = db.get_samples_for_training()
    assert len(training_samples_after) == 0
