import os
import threading
import time
from typing import Optional, Dict, Any
from pathlib import Path
from storage.database import Database
from training.dataset_builder import DatasetBuilder

class LoRATrainer:
    """Asynchronous LoRA Fine-tuning pipeline for Qwen3-ASR."""
    def __init__(self, db: Optional[Database] = None, output_dir: Optional[str] = None, profile_id: Optional[str] = None):
        from config import get_settings
        settings = get_settings()
        self.db = db or Database()
        self.profile_id = profile_id or "default"
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = str(settings.ADAPTERS_DIR / self.profile_id)
        self.builder = DatasetBuilder(self.db, profile_id=self.profile_id)

        self.is_training = False
        self.current_epoch = 0
        self.total_epochs = 0
        self.current_step = 0
        self.current_loss = 0.0
        self.status = "idle"  # idle | preparing | training | completed | failed
        self.last_error: Optional[str] = None

    def switch_profile(self, profile_id: str):
        """Switch profile for trainer."""
        from config import get_settings
        settings = get_settings()
        self.profile_id = profile_id.strip().lower() or "default"
        self.output_dir = str(settings.ADAPTERS_DIR / self.profile_id)
        self.builder = DatasetBuilder(self.db, profile_id=self.profile_id)

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_training": self.is_training,
            "status": self.status,
            "profile_id": self.profile_id,
            "current_epoch": self.current_epoch,
            "total_epochs": self.total_epochs,
            "current_step": self.current_step,
            "current_loss": round(self.current_loss, 4),
            "output_dir": self.output_dir,
            "last_error": self.last_error
        }

    def start_training(
        self,
        epochs: int = 3,
        lr: float = 1e-4,
        batch_size: int = 2,
        on_completed=None,
        asr_engine=None
    ) -> bool:
        if self.is_training:
            return False

        samples = self.builder.collect_samples()
        if not samples:
            self.status = "idle"
            self.last_error = "No reviewed samples available for training"
            return False

        self.is_training = True
        self.status = "preparing"
        self.total_epochs = epochs
        self.current_epoch = 0
        self.current_loss = 0.0
        self.last_error = None

        thread = threading.Thread(
            target=self._run_training_worker,
            args=(samples, epochs, lr, batch_size, on_completed, asr_engine),
            daemon=True
        )
        thread.start()
        return True

    def _run_training_worker(self, samples, epochs, lr, batch_size, on_completed, asr_engine=None):
        try:
            import torch
            import soundfile as sf
            from peft import LoraConfig, get_peft_model, PeftModel
            from torch.optim import AdamW

            print(f"[LoRATrainer] Starting REAL PyTorch LoRA training with {len(samples)} samples for {epochs} epochs...")
            self.status = "training"
            
            # 1. Get model & processor
            if asr_engine and asr_engine.is_loaded:
                engine = asr_engine
            else:
                from asr_engine.engine import ASREngine
                engine = ASREngine(lazy_load=False)

            raw_model = getattr(engine.model, "model", engine.model)
            thinker = getattr(raw_model, "thinker", None)
            target_model = getattr(thinker, "model", thinker)
            processor = engine.model.processor
            device = engine.device

            # 2. Configure LoRA on thinker text decoder model
            lora_config = LoraConfig(
                r=8,
                lora_alpha=32,
                target_modules=["q_proj", "v_proj"],
                lora_dropout=0.05,
                bias="none"
            )

            # If not already PeftModel, wrap it
            if isinstance(target_model, PeftModel):
                peft_model = target_model
            else:
                peft_model = get_peft_model(target_model, lora_config)
                if thinker is not None:
                    thinker.model = peft_model

            # Ensure all LoRA parameters are explicitly unfrozen for training
            peft_model.train()
            for name, param in peft_model.named_parameters():
                if "lora_" in name:
                    param.requires_grad = True

            trainable_params = [p for p in peft_model.parameters() if p.requires_grad]
            if not trainable_params:
                raise ValueError("No trainable LoRA parameters found in model.")
            optimizer = AdamW(trainable_params, lr=lr)

            total_steps = epochs * len(samples)
            step_count = 0

            # 3. Training Loop over reviewed audio-text pairs
            for epoch in range(1, epochs + 1):
                self.current_epoch = epoch

                for i, sample in enumerate(samples):
                    step_count += 1
                    self.current_step = step_count

                    audio_path = sample["audio_path"]
                    ground_truth = (sample.get("text") or sample.get("corrected_text") or "").strip()
                    if not os.path.exists(audio_path) or not ground_truth:
                        continue

                    wav, sr = sf.read(audio_path)
                    if sr != 16000:
                        import scipy.signal
                        num_samples = round(len(wav) * 16000.0 / sr)
                        wav = scipy.signal.resample(wav, num_samples)
                    if len(wav.shape) > 1:
                        wav = wav.mean(axis=1)

                    # Build prompt with target transcription text
                    prompt = f"<|im_start|>system\n<|im_end|>\n<|im_start|>user\n<|audio_start|><|audio_pad|><|audio_end|><|im_end|>\n<|im_start|>assistant\nlanguage Vietnamese<asr_text>{ground_truth}<|im_end|>"
                    
                    inputs = processor(text=prompt, audio=wav, return_tensors="pt")
                    # Move to model device
                    for k in inputs:
                        if isinstance(inputs[k], torch.Tensor):
                            if "input_features" in k and engine.dtype:
                                inputs[k] = inputs[k].to(device=device, dtype=engine.dtype)
                            else:
                                inputs[k] = inputs[k].to(device=device)

                    labels = inputs["input_ids"].clone()
                    # Mask prompt tokens with -100 so loss is only calculated on target transcription
                    asr_token_id = 151704
                    token_list = inputs["input_ids"][0].tolist()
                    if asr_token_id in token_list:
                        asr_idx = token_list.index(asr_token_id)
                        labels[0, :asr_idx + 1] = -100

                    # Forward pass through thinker
                    outputs = thinker(**inputs, labels=labels)
                    loss = outputs.loss

                    if loss is not None and not torch.isnan(loss):
                        loss.backward()
                        optimizer.step()
                        optimizer.zero_grad()
                        current_l = float(loss.item())
                        self.current_loss = current_l

                    time.sleep(0.02)

            # 4. Save trained adapter weights
            out_path = Path(self.output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            peft_model.save_pretrained(str(out_path))
            print(f"[LoRATrainer] Successfully trained and saved LoRA weights to {self.output_dir}")

            # 5. Mark processed samples in DB
            sample_ids = [s["id"] for s in samples]
            self.db.mark_samples_trained(sample_ids)

            self.status = "completed"
            self.is_training = False

            # Set model back to eval mode
            peft_model.eval()

            if on_completed:
                on_completed(self.output_dir)

        except Exception as e:
            self.status = "failed"
            self.is_training = False
            self.last_error = str(e)
            print(f"[LoRATrainer] Training error: {e}")
            import traceback
            traceback.print_exc()
