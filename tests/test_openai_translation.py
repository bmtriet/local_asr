import pytest
from unittest.mock import patch, MagicMock
from asr_engine.grammar import GrammarCorrector

def test_grammar_corrector_init_local():
    corrector = GrammarCorrector(lazy_load=True)
    assert corrector.provider in ["local", "remote_api"]

def test_grammar_corrector_set_config_remote():
    corrector = GrammarCorrector(lazy_load=True)
    corrector.set_config(
        provider="remote_api",
        api_base_url="http://localhost:11434/v1",
        api_key="my-key",
        api_model="deepseek-chat"
    )
    assert corrector.provider == "remote_api"
    assert corrector.api_base_url == "http://localhost:11434/v1"
    assert corrector.api_key == "my-key"
    assert corrector.api_model == "deepseek-chat"

def test_grammar_corrector_openai_api_call():
    corrector = GrammarCorrector(lazy_load=True)
    corrector.set_config(
        provider="remote_api",
        api_base_url="http://mock-ollama:11434/v1",
        api_key="test-key",
        api_model="qwen2.5:7b"
    )

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "現在我正在說越南語，希望輸出會是中文吧"
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=fake_response) as mock_post:
        result = corrector.correct("Hiện tại mình đang nói tiếng Việt và hy vọng là cái output nó sẽ ra tiếng hoa nhé", mode="chinese")
        assert "現在我正在說越南語" in result
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://mock-ollama:11434/v1/chat/completions"
        assert kwargs["json"]["model"] == "qwen2.5:7b"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        # Verify Vietnamese idiom normalization occurred before API call
        user_msg = kwargs["json"]["messages"][1]["content"]
        assert "tiếng Trung Quốc" in user_msg
        assert "tiếng hoa" not in user_msg
