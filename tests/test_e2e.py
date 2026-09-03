import pytest
from fastapi.testclient import TestClient
from web.api import app
from storage.database import Database
from training.dataset_builder import DatasetBuilder
from training.lora_trainer import LoRATrainer

client = TestClient(app)

def test_full_pipeline_flow(tmp_path):
    # 1. Database creation & recording save
    db_file = str(tmp_path / "e2e.db")
    db = Database(db_file)
    db.init_db()
    
    row_id = db.save_transcription("sample.wav", 1.8, "xin chao")
    assert row_id == 1

    # 2. Correction by user via API logic
    db.update_correction(row_id, "Xin chào")
    item = db.get_transcription_by_id(row_id)
    assert item["corrected_text"] == "Xin chào"
    assert item["is_reviewed"] == 1

    # 3. LoRA trainer collects sample and completes training cycle
    adapter_dir = str(tmp_path / "adapter")
    trainer = LoRATrainer(db=db, output_dir=adapter_dir)
    status = trainer.get_status()
    assert status["status"] == "idle"

    # Start training
    started = trainer.start_training(epochs=1)
    assert started is True

    # Wait for completion
    import time
    for _ in range(30):
        if not trainer.is_training:
            break
        time.sleep(0.1)

    assert trainer.status == "completed"
    assert (tmp_path / "adapter" / "adapter_config.json").exists()

    # Verify marked as trained
    pending = db.get_samples_for_training()
    assert len(pending) == 0
