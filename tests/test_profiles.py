import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from storage.database import Database
from asr_engine.vocabulary import VocabularyManager
from web.api import app

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_profiles.db"
    db = Database(str(db_file))
    db.init_db()
    return db

def test_database_profile_lifecycle(temp_db):
    # Check default profile
    profiles = temp_db.get_profiles()
    assert len(profiles) >= 1
    assert any(p["id"] == "default" for p in profiles)
    
    active = temp_db.get_active_profile()
    assert active["id"] == "default"

    # Create new profile
    assert temp_db.create_profile("user_b", "User B", "Marketing dept")
    profiles = temp_db.get_profiles()
    assert any(p["id"] == "user_b" for p in profiles)

    # Switch active profile
    assert temp_db.set_active_profile("user_b")
    assert temp_db.get_active_profile()["id"] == "user_b"

    # Save transcription for user_b
    t_id = temp_db.save_transcription("test.wav", 2.0, "Xin chao user b", profile_id="user_b")
    assert t_id > 0

    # Verify counts per profile
    count_b = temp_db.get_transcriptions_count(profile_id="user_b")
    count_default = temp_db.get_transcriptions_count(profile_id="default")
    assert count_b == 1
    assert count_default == 0

    # Delete profile user_b -> active profile falls back to default
    assert temp_db.delete_profile("user_b")
    assert temp_db.get_active_profile()["id"] == "default"

def test_vocabulary_manager_profile_isolation(tmp_path):
    # Test profile isolation in VocabularyManager
    p1_file = tmp_path / "profiles" / "user_1" / "vocabulary.json"
    p2_file = tmp_path / "profiles" / "user_2" / "vocabulary.json"

    mgr = VocabularyManager(file_path=p1_file, profile_id="user_1")
    mgr.upsert("FinTech", ["fin tech", "tai chinh cong nghe"], "Fintech domain")
    assert mgr.apply("Tôi làm fin tech") == "Tôi làm FinTech"

    # Switch to user_2
    mgr.file_path = p2_file
    mgr.profile_id = "user_2"
    mgr.load()
    mgr.upsert("BioTech", ["bio tech", "cong nghe sinh hoc"], "Biotech domain")
    assert mgr.apply("Tôi làm bio tech") == "Tôi làm BioTech"
    # user_2 doesn't have FinTech mapping
    assert mgr.apply("Tôi làm fin tech") == "Tôi làm fin tech"

def test_api_profile_endpoints():
    client = TestClient(app)
    
    # Get profiles
    res = client.get("/api/profiles")
    assert res.status_code == 200
    data = res.json()
    assert "profiles" in data
    assert "active_profile" in data

    # Create profile
    res_create = client.post("/api/profiles", json={
        "id": "alex_tech",
        "name": "Alex Tech",
        "description": "Tech lead profile"
    })
    assert res_create.status_code == 200

    # Switch to alex_tech
    res_switch = client.post("/api/profiles/active", json={"profile_id": "alex_tech"})
    assert res_switch.status_code == 200
    assert res_switch.json()["active_profile"]["id"] == "alex_tech"

    # Switch back to default
    res_back = client.post("/api/profiles/active", json={"profile_id": "default"})
    assert res_back.status_code == 200

    # Delete created profile
    res_del = client.delete("/api/profiles/alex_tech")
    assert res_del.status_code == 200
