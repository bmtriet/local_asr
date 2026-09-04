import re
from typing import Dict, Optional

DIGIT_WORDS = {
    'không': '0', 'khong': '0', '0': '0',
    'một': '1', 'mot': '1', 'mốt': '1', '1': '1',
    'hai': '2', '2': '2',
    'ba': '3', '3': '3',
    'bốn': '4', 'bon': '4', 'tư': '4', '4': '4',
    'năm': '5', 'nam': '5', 'lăm': '5', '5': '5',
    'sáu': '6', 'sau': '6', '6': '6',
    'bảy': '7', 'bay': '7', 'bẩy': '7', '7': '7',
    'tám': '8', 'tam': '8', '8': '8',
    'chín': '9', 'chin': '9', '9': '9'
}

TEEN_WORDS = {
    'mười': '10', 'mười một': '11', 'mười hai': '12', 'mười ba': '13',
    'mười bốn': '14', 'mười lăm': '15', 'mười sáu': '16', 'mười bảy': '17',
    'mười tám': '18', 'mười chín': '19'
}

class VietnameseNormalizer:
    """Fast Inverse Text Normalization (ITN) and user phrase replacement for Vietnamese ASR."""
    
    def __init__(self, db=None, vocab_mgr=None):
        self.db = db
        if vocab_mgr is not None:
            self.vocab_mgr = vocab_mgr
        else:
            try:
                from asr_engine.vocabulary import VocabularyManager
                self.vocab_mgr = VocabularyManager()
            except Exception:
                self.vocab_mgr = None

    def normalize(self, text: str) -> str:
        if not text or not text.strip():
            return text

        normalized = text.strip()

        # 1. Apply user custom vocabulary mapping from vocabulary.json (exact, spaced out, case variants)
        if self.vocab_mgr:
            try:
                normalized = self.vocab_mgr.apply(normalized)
            except Exception as e:
                print(f"[Normalizer] Error applying vocabulary mapping: {e}")

        # 2. Check user custom phrase replacements from database
        if self.db:
            try:
                replacements = self.db.get_user_phrase_replacements()
                norm_lower = normalized.lower()
                for raw, corr in replacements.items():
                    if raw in norm_lower:
                        # Case-insensitive replacement
                        pattern = re.compile(re.escape(raw), re.IGNORECASE)
                        normalized = pattern.sub(corr, normalized)
            except Exception as e:
                print(f"[Normalizer] Error fetching user replacements: {e}")

        # 2. Normalize spoken digit sequences (phone numbers, OTPs, numbers)
        normalized = self._normalize_digit_sequences(normalized)

        # 3. Normalize common time expressions (e.g., "16 giờ 30" -> "16:30")
        normalized = self._normalize_time_expressions(normalized)

        # 4. Normalize decimal and percentage numbers
        normalized = self._normalize_decimal_and_percentage(normalized)

        return normalized

    def _normalize_digit_sequences(self, text: str) -> str:
        """Convert sequences of spoken Vietnamese digits (like phone numbers) to digits."""
        tokens = text.split()
        result = []
        i = 0
        n = len(tokens)

        while i < n:
            clean_word = tokens[i].lower().strip('.,?!;:')
            if clean_word in DIGIT_WORDS:
                j = i
                seq = []
                while j < n and tokens[j].lower().strip('.,?!;:') in DIGIT_WORDS:
                    w_clean = tokens[j].lower().strip('.,?!;:')
                    seq.append((w_clean, tokens[j]))
                    j += 1

                # If sequence length >= 2 (e.g. phone number, OTP, multi-digit)
                if len(seq) >= 2:
                    digits = ''.join(DIGIT_WORDS[w[0]] for w in seq)
                    # Preserve trailing punctuation from last token if any
                    last_punct = re.search(r'[.,?!;:]+$', seq[-1][1])
                    punct_str = last_punct.group(0) if last_punct else ''
                    result.append(digits + punct_str)
                    i = j
                    continue
                else:
                    result.append(tokens[i])
                    i += 1
            else:
                result.append(tokens[i])
                i += 1

        return ' '.join(result)

    def _normalize_time_expressions(self, text: str) -> str:
        """Normalize expressions like '16 giờ 30' or 'mười sáu giờ ba mươi' to '16:30'."""
        # Pattern like "16 giờ 30 phút" -> "16:30"
        text = re.sub(r'(\b\d{1,2})\s*giờ\s*(\d{1,2})\s*(phút)?\b', r'\1:\2', text, flags=re.IGNORECASE)
        # Pattern like "16 giờ" -> "16h" or "16:00"
        text = re.sub(r'(\b\d{1,2})\s*giờ\b', r'\1h', text, flags=re.IGNORECASE)
        return text

    def _normalize_decimal_and_percentage(self, text: str) -> str:
        """Normalize expressions like 'không phẩy năm' -> '0.5', 'mười phần trăm' -> '10%'."""
        # Decimal: "X phẩy Y" / "X chấm Y" where X and Y are digits
        text = re.sub(r'(\b\d+)\s*(phẩy|chấm)\s*(\d+)\b', r'\1.\3', text, flags=re.IGNORECASE)
        # Percentage: "X phần trăm" or "X %" -> "X%"
        text = re.sub(r'(\b\d+)\s*(?:phần\s*trăm|%)\b', r'\1%', text, flags=re.IGNORECASE)
        text = re.sub(r'(\b\d+)\s+%', r'\1%', text)
        return text
