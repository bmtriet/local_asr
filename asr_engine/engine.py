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

        self.model = None
        self.is_loaded = False
        self.active_adapter_name: Optional[str] = None
        
        if not lazy_load:
            self.load_model()

    def load_model(self):
        """Loads Qwen3ASR model via official qwen_asr package directly onto GPU."""
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
        print("[ASREngine] Model loaded successfully on GPU.")

    def load_lora_adapter(self, adapter_dir: str, adapter_name: str = "custom_lora"):
        """Attach a trained PEFT LoRA adapter dynamically."""
        if not self.is_loaded:
            self.load_model()
            
        if not os.path.exists(adapter_dir):
            raise FileNotFoundError(f"LoRA adapter directory does not exist: {adapter_dir}")

        from peft import PeftModel
        # Access underlying torch model inside Qwen3ASRModel
        raw_model = getattr(self.model, "model", self.model)
        if isinstance(raw_model, PeftModel):
            raw_model.load_adapter(adapter_dir, adapter_name=adapter_name)
            raw_model.set_adapter(adapter_name)
        else:
            setattr(self.model, "model", PeftModel.from_pretrained(raw_model, adapter_dir, adapter_name=adapter_name))
        
        self.active_adapter_name = adapter_name
        print(f"[ASREngine] Loaded and activated LoRA adapter: {adapter_name} from {adapter_dir}")

    def unload_lora_adapter(self):
        """Unload LoRA adapter, returning to base model weights."""
        raw_model = getattr(self.model, "model", self.model)
        from peft import PeftModel
        if isinstance(raw_model, PeftModel):
            setattr(self.model, "model", raw_model.get_base_model())
            self.active_adapter_name = None
            print("[ASREngine] Unloaded LoRA adapter.")

    def transcribe(self, audio_source: Union[str, np.ndarray], sample_rate: int = 16000) -> str:
        """Transcribe audio from a file path or numpy array (mono 16kHz float32)."""
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

        results = self.model.transcribe((wav, sample_rate))
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
