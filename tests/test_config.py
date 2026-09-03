from config import get_settings

def test_default_settings():
    settings = get_settings()
    assert settings.HOTKEY == "ctrl+alt+space"
    assert settings.MODEL_NAME == "Qwen/Qwen3-ASR-0.6B"
    assert settings.DB_PATH.endswith("local_asr.db")
