import pytest
from unittest.mock import MagicMock
from asr_engine.grammar import GrammarCorrector

def test_grammar_corrector_strips_conversational_chatter():
    corrector = GrammarCorrector(lazy_load=True)
    corrector.is_loaded = True
    
    # Mock LLM pipeline output containing chatter preamble
    corrector.pipeline = MagicMock(return_value=[{
        "generated_text": "Đúng, tôi sẽ làm điều đó cho bạn. Dưới đây là đoạn văn bản đã được chỉnh sửa: Tôi đang truy cập hệ thống."
    }])

    result = corrector.correct("tôi đang truy cập hệ thống")
    assert result == "Tôi đang truy cập hệ thống."
    assert "Đúng, tôi sẽ làm" not in result
    assert "Dưới đây là" not in result

def test_grammar_corrector_strips_english_chatter():
    corrector = GrammarCorrector(lazy_load=True)
    corrector.is_loaded = True
    
    corrector.pipeline = MagicMock(return_value=[{
        "generated_text": "Certainly! Here is the translated text: How are you today?"
    }])

    result = corrector.correct("bạn hôm nay thế nào", mode="english")
    assert result == "How are you today?"
    assert "Certainly" not in result
    assert "Here is" not in result
