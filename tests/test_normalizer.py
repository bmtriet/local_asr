import pytest
from asr_engine.normalizer import VietnameseNormalizer
from unittest.mock import MagicMock

def test_vietnamese_normalizer_phone_numbers():
    norm = VietnameseNormalizer()
    
    # Standard 10-digit Vietnamese phone number
    assert norm.normalize("Không chín tám bảy ba một một tám sáu một") == "0987311861"
    assert norm.normalize("số của tôi là không chín tám bảy ba một một tám sáu một") == "số của tôi là 0987311861"
    assert norm.normalize("0 chín tám bảy ba một một tám sáu một.") == "0987311861."

def test_vietnamese_normalizer_digit_sequences():
    norm = VietnameseNormalizer()
    assert norm.normalize("một hai ba bốn năm sáu") == "123456"
    assert norm.normalize("mã thẻ một chín hai một") == "mã thẻ 1921"

def test_vietnamese_normalizer_time_and_percentage():
    norm = VietnameseNormalizer()
    assert norm.normalize("16 giờ 30 phút") == "16:30"
    assert norm.normalize("tăng trưởng 15 phần trăm") == "tăng trưởng 15%"
    assert norm.normalize("kích thước 0 phẩy 5") == "kích thước 0.5"

def test_vietnamese_normalizer_user_replacements():
    mock_db = MagicMock()
    mock_db.get_user_phrase_replacements.return_value = {
        "quen": "Qwen",
        "mô đột": "Model"
    }
    norm = VietnameseNormalizer(db=mock_db)
    assert norm.normalize("Tôi dùng quen") == "Tôi dùng Qwen"
    assert norm.normalize("mô đột mới") == "Model mới"
