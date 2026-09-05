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

_VN_DIGIT_MAP = {
    'không': 0, 'khong': 0,
    'một': 1, 'mot': 1, 'mốt': 1,
    'hai': 2,
    'ba': 3,
    'bốn': 4, 'bon': 4, 'tư': 4,
    'năm': 5, 'nam': 5, 'lăm': 5,
    'sáu': 6, 'sau': 6,
    'bảy': 7, 'bay': 7, 'bẩy': 7,
    'tám': 8, 'tam': 8,
    'chín': 9, 'chin': 9
}

_UNIT_GROUP = '(?:' + '|'.join(sorted(_VN_DIGIT_MAP.keys(), key=len, reverse=True)) + ')'
_TENS_GROUP = '(?:' + '|'.join(sorted(['hai', 'ba', 'bốn', 'bon', 'tư', 'năm', 'nam'], key=len, reverse=True)) + ')'
_VN_TIME_NUM_PATTERN = rf'(?:\d{{1,2}}|(?:mười|muoi)(?:\s+{_UNIT_GROUP})?|{_TENS_GROUP}\s+(?:mươi|muoi)(?:\s+{_UNIT_GROUP})?|{_UNIT_GROUP})'

def _parse_vn_time_number(text: str) -> Optional[int]:
    """Parse Vietnamese spoken number representation from 0 to 59 or numeric digit string."""
    if not text:
        return None
    words = text.lower().strip().split()
    if not words:
        return None
    if len(words) == 1 and words[0].isdigit():
        val = int(words[0])
        return val if 0 <= val <= 59 else None
    if len(words) == 1 and words[0] in _VN_DIGIT_MAP:
        return _VN_DIGIT_MAP[words[0]]
    if len(words) == 1 and words[0] in ['mười', 'muoi']:
        return 10
    if len(words) == 2 and words[0] in ['mười', 'muoi'] and words[1] in _VN_DIGIT_MAP:
        return 10 + _VN_DIGIT_MAP[words[1]]
    if len(words) == 2 and words[1] in ['mươi', 'muoi'] and words[0] in _VN_DIGIT_MAP and _VN_DIGIT_MAP[words[0]] >= 2:
        return _VN_DIGIT_MAP[words[0]] * 10
    if len(words) == 3 and words[1] in ['mươi', 'muoi'] and words[0] in _VN_DIGIT_MAP and words[2] in _VN_DIGIT_MAP and _VN_DIGIT_MAP[words[0]] >= 2:
        return _VN_DIGIT_MAP[words[0]] * 10 + _VN_DIGIT_MAP[words[2]]
    return None

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

        # 3. Normalize common time expressions (e.g. "Mười giờ ba mươi phút" -> "10:30", "16 giờ 30" -> "16:30")
        # Run before digit sequences to avoid splitting time expressions into isolated digits
        normalized = self._normalize_time_expressions(normalized)

        # 4. Normalize spoken digit sequences (phone numbers, OTPs, numbers)
        normalized = self._normalize_digit_sequences(normalized)

        # 5. Normalize decimal and percentage numbers
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
        """Normalize expressions like 'Mười giờ ba mươi phút' -> '10:30', '16 giờ 30' -> '16:30'."""
        # 1. <hour> giờ kém <min> [phút] -> (hour-1):(60-min)
        pat_kem = re.compile(rf'\b({_VN_TIME_NUM_PATTERN})\s*giờ\s*kém\s*({_VN_TIME_NUM_PATTERN})(?:\s*phút)?\b', re.IGNORECASE)
        def repl_kem(m):
            h = _parse_vn_time_number(m.group(1))
            kem_min = _parse_vn_time_number(m.group(2))
            if h is not None and kem_min is not None and 1 <= h <= 24 and 1 <= kem_min < 60:
                target_h = (h - 1) if h > 0 else 23
                target_min = 60 - kem_min
                return f'{target_h}:{target_min:02d}'
            return m.group(0)
        text = pat_kem.sub(repl_kem, text)

        # 2. <hour> giờ rưỡi -> <hour>:30
        pat_ruoi = re.compile(rf'\b({_VN_TIME_NUM_PATTERN})\s*giờ\s*rưỡi\b', re.IGNORECASE)
        def repl_ruoi(m):
            h = _parse_vn_time_number(m.group(1))
            if h is not None and 0 <= h <= 24:
                return f'{h}:30'
            return m.group(0)
        text = pat_ruoi.sub(repl_ruoi, text)

        # 3. <hour> giờ <min> phút -> <hour>:<min:02d>
        pat_with_phut = re.compile(rf'\b({_VN_TIME_NUM_PATTERN})\s*giờ\s*({_VN_TIME_NUM_PATTERN})\s*phút\b', re.IGNORECASE)
        def repl_with_phut(m):
            h = _parse_vn_time_number(m.group(1))
            min_val = _parse_vn_time_number(m.group(2))
            if h is not None and min_val is not None and 0 <= h <= 24 and 0 <= min_val <= 59:
                return f'{h}:{min_val:02d}'
            return m.group(0)
        text = pat_with_phut.sub(repl_with_phut, text)

        # 4. <hour> giờ <min> -> <hour>:<min:02d>
        pat_without_phut = re.compile(rf'\b({_VN_TIME_NUM_PATTERN})\s*giờ\s*({_VN_TIME_NUM_PATTERN})\b', re.IGNORECASE)
        def repl_without_phut(m):
            h = _parse_vn_time_number(m.group(1))
            min_val = _parse_vn_time_number(m.group(2))
            if h is not None and min_val is not None and 0 <= h <= 24 and 0 <= min_val <= 59:
                return f'{h}:{min_val:02d}'
            return m.group(0)
        text = pat_without_phut.sub(repl_without_phut, text)

        # 5. <hour> giờ -> <hour>h
        pat_hour_only = re.compile(rf'\b({_VN_TIME_NUM_PATTERN})\s*giờ\b', re.IGNORECASE)
        def repl_hour_only(m):
            h = _parse_vn_time_number(m.group(1))
            if h is not None and 0 <= h <= 24:
                return f'{h}h'
            return m.group(0)
        text = pat_hour_only.sub(repl_hour_only, text)

        return text

    def _normalize_decimal_and_percentage(self, text: str) -> str:
        """Normalize expressions like 'không phẩy năm' -> '0.5', 'mười phần trăm' -> '10%'."""
        # Decimal: "X phẩy Y" / "X chấm Y" where X and Y are digits
        text = re.sub(r'(\b\d+)\s*(phẩy|chấm)\s*(\d+)\b', r'\1.\3', text, flags=re.IGNORECASE)
        # Percentage: "X phần trăm" or "X %" -> "X%"
        text = re.sub(r'(\b\d+)\s*(?:phần\s*trăm|%)\b', r'\1%', text, flags=re.IGNORECASE)
        text = re.sub(r'(\b\d+)\s+%', r'\1%', text)
        return text
