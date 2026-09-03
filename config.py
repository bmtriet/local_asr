import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = BASE_DIR / "data"
    RECORDINGS_DIR: Path = DATA_DIR / "recordings"
    ADAPTERS_DIR: Path = DATA_DIR / "adapters"
    DB_PATH: str = str(DATA_DIR / "local_asr.db")
    
    # ASR Model settings
    MODEL_NAME: str = "Qwen/Qwen3-ASR-0.6B"
    DEVICE: str = "cuda"
    TORCH_DTYPE: str = "bfloat16"
    CPU_THREADS: int = min(4, os.cpu_count() or 4)
    
    # Grammar Correction & Translation Model settings
    GRAMMAR_MODEL_NAME: str = "Qwen/Qwen2.5-0.5B-Instruct"
    GRAMMAR_CORRECTION_ENABLED: bool = False
    TRANSLATION_TARGET: str = "english" # "english" or "chinese"
    ADD_ORIGIN_PHRASE: bool = False
    
    # Hotkey & Input injection settings
    HOTKEY: str = "ctrl+alt+space"
    SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    
    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    model_config = SettingsConfigDict(env_prefix="LOCAL_ASR_", extra="ignore")

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        _settings.ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    return _settings
