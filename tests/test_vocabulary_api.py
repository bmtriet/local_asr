import pytest
from fastapi.testclient import TestClient
from web.api import app, vocab_mgr

@pytest.fixture
def client():
    return TestClient(app)

def test_api_get_vocabulary(client):
    res = client.get("/api/vocabulary")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    targets = [item["target"] for item in data["items"]]
    assert "IFM" in targets
    assert "Global User" in targets
    assert "PAB" in targets

def test_api_test_vocabulary_mapping(client):
    res = client.post("/api/vocabulary/test", json={"text": "tôi dùng ifm và pab với global user"})
    assert res.status_code == 200
    data = res.json()
    assert data["changed"] is True
    assert "IFM" in data["mapped"]
    assert "PAB" in data["mapped"]
    assert "Global User" in data["mapped"]

def test_api_upsert_and_delete_vocabulary(client):
    # Add new
    res = client.post("/api/vocabulary", json={
        "target": "VNG Corporation",
        "aliases": ["vng", "v n g", "vi en gi"],
        "description": "Tập đoàn công nghệ"
    })
    assert res.status_code == 200
    
    # Test mapping new word
    res_test = client.post("/api/vocabulary/test", json={"text": "làm việc tại v n g"})
    assert "VNG Corporation" in res_test.json()["mapped"]

    # Delete word
    res_del = client.delete("/api/vocabulary/VNG%20Corporation")
    assert res_del.status_code == 200

    # Ensure removed
    res_test_after = client.post("/api/vocabulary/test", json={"text": "làm việc tại v n g"})
    assert "VNG Corporation" not in res_test_after.json()["mapped"]
