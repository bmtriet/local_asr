import os
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Optional, Union

class ASREngine:
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        dtype: Optional[str] = None,
        lazy_load: bool = False
    ):
        from config import get_settings
        settings = get_settings()
        
        self.model_name = model_name or settings.MODEL_NAME
        self.device = device or (settings.DEVICE if torch.cuda.is_available() else "cpu")
        self.dtype = getattr(torch, dtype or settings.TORCH_DTYPE, torch.bfloat16)
        if self.device == "cpu":
            self.dtype = torch.float32
            torch.set_num_threads(settings.CPU_THREADS)
            print(f"[ASREngine] Running in CPU-only mode (intra-op threads: {settings.CPU_THREADS})")

        self.model = None
        self.is_loaded = False
        self.active_adapter_name: Optional[str] = None
        
        if not lazy_load:
            self.load_model()

    def load_model(self):
        """Loads Qwen3ASR model via official qwen_asr package."""
        if self.is_loaded:
            return

        from qwen_asr import Qwen3ASRModel

        device_map = "cuda:0" if "cuda" in self.device and torch.cuda.is_available() else "cpu"
        print(f"[ASREngine] Loading {self.model_name} onto {device_map} ({self.dtype})...")
        
        self.model = Qwen3ASRModel.from_pretrained(
            self.model_name,
            dtype=self.dtype,
            device_map=device_map
        )
        self.is_loaded = True
        print(f"[ASREngine] Model loaded successfully on {device_map}.")
        
        # Check if trained LoRA adapter with weights exists and auto-load it
        from config import get_settings
        adapter_path = get_settings().ADAPTERS_DIR / "lora_latest"
        has_config = (adapter_path / "adapter_config.json").exists()
        has_weights = (adapter_path / "adapter_model.safetensors").exists() or (adapter_path / "adapter_model.bin").exists()
        if has_config and has_weights:
            try:
                self.load_lora_adapter(str(adapter_path))
            except Exception as e:
                print(f"[ASREngine] Could not auto-load LoRA adapter: {e}")

    def _get_thinker_model(self):
        """Safely retrieve the inner thinker text decoder model for PEFT."""
        raw_model = getattr(self.model, "model", self.model)
        thinker = getattr(raw_model, "thinker", None)
        if thinker is not None:
            return getattr(thinker, "model", thinker)
        return raw_model

    def load_lora_adapter(self, adapter_dir: str, adapter_name: str = "custom_lora"):
        """Attach a trained PEFT LoRA adapter dynamically to the thinker text model."""
        if not self.is_loaded:
            self.load_model()
            
        if not os.path.exists(adapter_dir):
            raise FileNotFoundError(f"LoRA adapter directory does not exist: {adapter_dir}")

        from peft import PeftModel
        target_model = self._get_thinker_model()
        if isinstance(target_model, PeftModel):
            target_model.load_adapter(adapter_dir, adapter_name=adapter_name)
            target_model.set_adapter(adapter_name)
        else:
            peft_m = PeftModel.from_pretrained(target_model, adapter_dir, adapter_name=adapter_name)
            # Reattach to thinker
            raw_model = getattr(self.model, "model", self.model)
            if hasattr(raw_model, "thinker"):
                raw_model.thinker.model = peft_m
        
        self.active_adapter_name = adapter_name
        print(f"[ASREngine] Loaded and activated LoRA adapter: {adapter_name} from {adapter_dir}")

    def switch_profile_adapter(self, profile_id: str):
        """Switch active LoRA adapter to profile's adapter if it exists, otherwise unload."""
        from config import get_settings
        settings = get_settings()
        clean_id = profile_id.strip().lower() or "default"
        
        # Check both data/adapters/<profile_id> and data/adapters/lora_latest (for default legacy)
        adapter_path = settings.ADAPTERS_DIR / clean_id
        if not adapter_path.exists() and clean_id == "default":
            legacy_path = settings.ADAPTERS_DIR / "lora_latest"
            if legacy_path.exists():
                adapter_path = legacy_path

        has_config = (adapter_path / "adapter_config.json").exists()
        has_weights = (adapter_path / "adapter_model.safetensors").exists() or (adapter_path / "adapter_model.bin").exists()

        if has_config and has_weights:
            try:
                self.load_lora_adapter(str(adapter_path), adapter_name=clean_id)
                print(f"[ASREngine] Switched to LoRA adapter for profile '{clean_id}'")
            except Exception as e:
                print(f"[ASREngine] Failed loading adapter for profile '{clean_id}': {e}")
        else:
            if self.active_adapter_name:
                self.unload_lora_adapter()
                print(f"[ASREngine] Profile '{clean_id}' has no trained adapter. Reverted to base model.")

    def transcribe(self, audio_source: Union[str, np.ndarray], sample_rate: int = 16000, context: str = "") -> str:
        """Transcribe audio with optional context hotword biasing."""
        if not self.is_loaded:
            self.load_model()

        if isinstance(audio_source, (str, Path)):
            audio_path = str(audio_source)
            wav, sr = sf.read(audio_path)
            if sr != sample_rate:
                import scipy.signal
                number_of_samples = round(len(wav) * float(sample_rate) / sr)
                wav = scipy.signal.resample(wav, number_of_samples)
            if len(wav.shape) > 1:
                wav = wav.mean(axis=1)
        else:
            wav = audio_source
            if len(wav.shape) > 1:
                wav = wav.mean(axis=1)

        wav = wav.astype(np.float32)

        # Pass user vocabulary / keywords context to Qwen3-ASR
        results = self.model.transcribe((wav, sample_rate), context=context or "")
        if not results:
            return ""

        first_res = results[0]
        text = getattr(first_res, "text", "")
        if not text and isinstance(first_res, dict):
            text = first_res.get("text", "")
        text = str(text).strip()
        if text:
            text = text[0].upper() + text[1:]
        return text
