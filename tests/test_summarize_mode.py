import pytest
from unittest.mock import MagicMock
from asr_engine.grammar import GrammarCorrector

def test_grammar_summarize_prompt_construction():
    corrector = GrammarCorrector(lazy_load=True)
    corrector._call_openai_api = MagicMock(return_value="Dự án trễ hạn vì thiếu nhân lực; cần thắt chặt thời gian tới.")
    corrector.provider = "remote_api"

    raw_text = "Ờ thì cái dự án của chúng ta hiện tại là nó đang bị trễ hạn là do bên mình thiếu nhân sự đó, nên là sắp tới cần phải quản lý thời gian chặt chẽ lại."
    result = corrector.correct(raw_text, mode="summarize", custom_vocab="ASR, Qwen")

    assert corrector._call_openai_api.called
    call_args = corrector._call_openai_api.call_args[0][0] # messages
    sys_msg = call_args[0]["content"]
    user_msg = call_args[1]["content"]

    # Verify key directives in prompt
    assert "AI Summarizer & Executive Polish" in sys_msg
    assert "Lược bỏ triệt để các từ ngữ ngập ngừng" in sys_msg
    assert "BẮT BUỘC XUẤT RA BẰNG TIẾNG VIỆT 100%" in sys_msg
    assert "ASR, Qwen" in sys_msg
    assert raw_text in user_msg
    assert "Dự án trễ hạn" in result

def test_grammar_summarize_english_prompt_preservation():
    corrector = GrammarCorrector(lazy_load=True)
    corrector._call_openai_api = MagicMock(return_value="Reschedule meeting to tomorrow due to today's conflicts.")
    corrector.provider = "remote_api"

    raw_text = "Well um I think we should basically reschedule the meeting to tomorrow because everybody is busy today."
    result = corrector.correct(raw_text, mode="summarize")

    assert "Reschedule" in result
