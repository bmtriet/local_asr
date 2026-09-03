import os
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Optional, Union
from peft import PeftModel

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
        self.processor = None
        self.is_loaded = False
        self.active_adapter_name: Optional[str] = None
        
        if not lazy_load:
            self.load_model()

    def load_model(self):
        """Loads Qwen3ASR model and processor onto the selected device."""
        if self.is_loaded:
            return

        from transformers import AutoProcessor, Qwen3ASRForConditionalGeneration

        print(f"Loading ASR model {self.model_name} on {self.device} ({self.dtype})...")
        self.processor = AutoProcessor.from_pretrained(self.model_name)
        self.model = Qwen3ASRForConditionalGeneration.from_pretrained(
            self.model_name,
            torch_dtype=self.dtype
        ).to(self.device)
        self.model.eval()
        self.is_loaded = True
        print("ASR model loaded successfully.")

    def load_lora_adapter(self, adapter_dir: str, adapter_name: str = "custom_lora"):
        """Attach a trained PEFT LoRA adapter dynamically."""
        if not self.is_loaded:
            self.load_model()
            
        if not os.path.exists(adapter_dir):
            raise FileNotFoundError(f"LoRA adapter directory does not exist: {adapter_dir}")

        if isinstance(self.model, PeftModel):
            self.model.load_adapter(adapter_dir, adapter_name=adapter_name)
            self.model.set_adapter(adapter_name)
        else:
            self.model = PeftModel.from_pretrained(
                self.model,
                adapter_dir,
                adapter_name=adapter_name
            )
        self.active_adapter_name = adapter_name
        print(f"Loaded and activated LoRA adapter: {adapter_name} from {adapter_dir}")

    def unload_lora_adapter(self):
        """Unload LoRA adapter, returning to base model weights."""
        if isinstance(self.model, PeftModel):
            self.model = self.model.get_base_model()
            self.active_adapter_name = None
            print("Unloaded LoRA adapter. Reverted to base model.")

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

        inputs = self.processor(
            audio=wav,
            sampling_rate=sample_rate,
            return_tensors="pt"
        )
        
        # Move tensors to model device and dtype
        input_features = inputs.get("input_features")
        if input_features is not None:
            input_features = input_features.to(self.device, dtype=self.dtype)
            inputs["input_features"] = input_features
        else:
            for k, v in inputs.items():
                if isinstance(v, torch.Tensor):
                    inputs[k] = v.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=256)
            
        transcription = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return transcription.strip()
