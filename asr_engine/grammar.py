import torch
from transformers import pipeline
from config import get_settings

class GrammarCorrector:
    def __init__(self, lazy_load: bool = False):
        self.settings = get_settings()
        self.model_name = self.settings.GRAMMAR_MODEL_NAME
        self.device = self.settings.DEVICE if torch.cuda.is_available() else "cpu"
        self.dtype = getattr(torch, self.settings.TORCH_DTYPE, torch.bfloat16)
        if self.device == "cpu":
            self.dtype = torch.float32

        self.pipeline = None
        self.is_loaded = False
        
        if not lazy_load:
            self.load_model()

    def load_model(self):
        if self.is_loaded:
            return

        device_map = "cuda:0" if "cuda" in self.device and torch.cuda.is_available() else "cpu"
        print(f"[GrammarCorrector] Loading {self.model_name} onto {device_map} ({self.dtype})...")
        
        # Use transformers pipeline
        self.pipeline = pipeline(
            "text-generation",
            model=self.model_name,
            device_map=device_map,
            dtype=self.dtype,
        )
        self.is_loaded = True
        print(f"[GrammarCorrector] Model loaded successfully on {device_map}.")

    def correct(self, text: str, mode: str = "normal", custom_vocab: str = "") -> str:
        """Corrects grammar and spelling, or translates based on the selected mode."""
        if not text.strip():
            return text
            
        if not self.is_loaded:
            self.load_model()
            
        if mode == "english":
            system_prompt = "You are an expert translator. Translate the input text to English. If the text is ALREADY in English, simply polish and correct its grammar in English. Output ONLY the English text. Do not add any explanations or conversational filler. Preserve formatting."
        elif mode == "chinese":
            system_prompt = "You are an expert translator. Translate the input text to Traditional Chinese (Phồn thể - 繁體中文). If the text is ALREADY in Chinese, simply polish and correct its grammar. Output ONLY the Traditional Chinese text. Do not add any explanations or conversational filler. Preserve formatting."
        else:
            system_prompt = "Bạn là trợ lý chỉnh sửa chính tả và dấu câu cho văn bản sau khi nhận diện giọng nói. Hãy sửa lỗi ngữ pháp, thêm dấu câu nếu cần. Hãy chuyển các số nói (số điện thoại, mã số, ngày giờ, số đếm) sang chữ số tự nhiên (Ví dụ: 'không chín tám bảy ba một một tám sáu một' -> '0987311861', 'mười sáu giờ ba mươi' -> '16:30'). TUYỆT ĐỐI GIỮ NGUYÊN NGÔN NGỮ GỐC (tiếng Anh giữ nguyên tiếng Anh, tiếng Việt giữ nguyên tiếng Việt), KHÔNG DỊCH. Chỉ xuất ra văn bản sau khi sửa, không giải thích gì thêm."

        if custom_vocab:
            system_prompt += f"\nLưu ý đặc biệt các từ ngữ / thuật ngữ / cách viết hoa ưu tiên của người dùng: {custom_vocab}."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        print(f"[GrammarCorrector] Correcting: '{text}'")
        
        try:
            outputs = self.pipeline(
                messages,
                max_new_tokens=256,
                do_sample=False, # Use greedy decoding for correction
                return_full_text=False
            )
            
            corrected = outputs[0]["generated_text"].strip()
            print(f"[GrammarCorrector] Result: '{corrected}'")
            
            if corrected:
                corrected = corrected[0].upper() + corrected[1:]
                return corrected
        except Exception as e:
            print(f"[GrammarCorrector] Error during correction: {e}")
            
        return text # fallback to original text if fails
