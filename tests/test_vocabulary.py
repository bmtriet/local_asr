import pytest
from pathlib import Path
from asr_engine.vocabulary import VocabularyManager

@pytest.fixture
def temp_vocab_file(tmp_path):
    f = tmp_path / "vocabulary.json"
    return f

def test_vocabulary_defaults(temp_vocab_file):
    mgr = VocabularyManager(file_path=temp_vocab_file)
    assert temp_vocab_file.exists()
    items = mgr.get_all()
    targets = [i["target"] for i in items]
    assert "IFM" in targets
    assert "Global User" in targets
    assert "PAB" in targets

def test_vocabulary_apply_exact_and_case():
    mgr = VocabularyManager()
    assert mgr.apply("Hôm nay dùng ifm") == "Hôm nay dùng IFM"
    assert mgr.apply("Truy cập global user ngay") == "Truy cập Global User ngay"
    assert mgr.apply("gửi cho pab nhé") == "gửi cho PAB nhé"

def test_vocabulary_apply_spaced_out_and_variations():
    mgr = VocabularyManager()
    # Spaced acronyms
    assert mgr.apply("hệ thống i f m đang chạy") == "hệ thống IFM đang chạy"
    assert mgr.apply("phòng ban p a b") == "phòng ban PAB"
    
    # Phrase variants
    assert mgr.apply("tài khoản globaluser của tôi") == "tài khoản Global User của tôi"
    assert mgr.apply("đăng nhập glo bal user") == "đăng nhập Global User"

def test_vocabulary_word_boundaries():
    mgr = VocabularyManager()
    # Shouldn't replace inside unrelated words
    # e.g., 'pablo' shouldn't become 'PABlo'
    assert mgr.apply("pablo picasso") == "pablo picasso"

def test_vocabulary_context_string():
    mgr = VocabularyManager()
    ctx = mgr.get_context_string()
    assert "IFM" in ctx
    assert "Global User" in ctx
    assert "PAB" in ctx

def test_vocabulary_upsert_and_delete(temp_vocab_file):
    mgr = VocabularyManager(file_path=temp_vocab_file)
    assert mgr.upsert("OpenAI", ["open ai", "open-ai"], "Công ty AI")
    assert mgr.apply("Tôi thích open ai") == "Tôi thích OpenAI"
    
    # Delete
    assert mgr.delete("OpenAI")
    assert mgr.apply("Tôi thích open ai") == "Tôi thích open ai"
