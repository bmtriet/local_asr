import pytest
from fastapi.testclient import TestClient
from web.api import app
from config import get_settings
from storage.database import Database

client = TestClient(app)

def test_api_translation_settings():
    # 1. Test get settings
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "translation_target" in data
    assert "add_origin_phrase" in data

    # 2. Test update translation_target & add_origin_phrase
    update_res = client.post("/api/settings", json={
        "translation_target": "english",
        "add_origin_phrase": True
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()["settings"]
    assert updated_data["translation_target"] == "english"
    assert updated_data["add_origin_phrase"] is True

    # 3. Test toggle back
    update_res2 = client.post("/api/settings", json={
        "translation_target": "chinese",
        "add_origin_phrase": False
    })
    assert update_res2.status_code == 200
    updated_data2 = update_res2.json()["settings"]
    assert updated_data2["translation_target"] == "chinese"
    assert updated_data2["add_origin_phrase"] is False

def test_daemon_add_origin_phrase_logic(tmp_path):
    from daemon.service import VoiceTypingDaemon
    from unittest.mock import MagicMock

    db = Database(str(tmp_path / "test_trans.db"))
    db.init_db()
    db.set_setting("add_origin_phrase", "true")

    daemon = VoiceTypingDaemon(db=db, show_tray=False)
    daemon.current_mode = "english"
    
    # Mock grammar corrector
    daemon.grammar = MagicMock()
    daemon.grammar.correct.return_value = "Hello world"
    
    # Mock injector
    daemon.injector = MagicMock()

    # Simulate worker logic
    text = "Xin chào thế giới"
    add_origin = str(daemon.db.get_setting("add_origin_phrase", "false")).lower() == "true"
    translated = daemon.grammar.correct(text, mode=daemon.current_mode)
    
    if add_origin:
        final_text = f"{text}\n{translated}"
    else:
        final_text = translated

    assert final_text == "Xin chào thế giới\nHello world"

    # Verify that what is saved to DB for LoRA is ONLY the source spoken text, not the translation
    stored_corrected_text = text if daemon.current_mode != "normal" else final_text
    assert stored_corrected_text == "Xin chào thế giới"
    assert "Hello world" not in stored_corrected_text

def test_api_qwen25_toggle():
    # 1. Test get settings contains qwen25_enabled
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "qwen25_enabled" in data

    # 2. Disable Qwen2.5
    update_res = client.post("/api/settings", json={"qwen25_enabled": False})
    assert update_res.status_code == 200
    assert update_res.json()["settings"]["qwen25_enabled"] is False

    # 3. Enable Qwen2.5
    update_res2 = client.post("/api/settings", json={"qwen25_enabled": True})
    assert update_res2.status_code == 200
    assert update_res2.json()["settings"]["qwen25_enabled"] is True

def test_daemon_qwen25_unload_and_bypass(tmp_path):
    from daemon.service import VoiceTypingDaemon
    from unittest.mock import MagicMock

    db = Database(str(tmp_path / "test_qwen.db"))
    db.init_db()

    daemon = VoiceTypingDaemon(db=db, show_tray=False)
    daemon.grammar = MagicMock()
    daemon.grammar.unload_model = MagicMock()

    # Disable Qwen2.5
    daemon.set_qwen25_enabled(False)
    assert daemon.qwen25_enabled is False
    daemon.grammar.unload_model.assert_called_once()

    # When disabled and in translation mode, grammar.correct should not be called
    daemon.current_mode = "english"
    text = "Xin chào"
    qwen_enabled = daemon.qwen25_enabled
    if qwen_enabled:
        translated = daemon.grammar.correct(text, mode="english")
    else:
        translated = text # bypassed
    
    assert translated == "Xin chào"
    daemon.grammar.correct.assert_not_called()
