import pytest
from fastapi.testclient import TestClient
from web.api import app

client = TestClient(app)

def test_api_status():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "model" in data

def test_get_history():
    res = client.get("/api/history")
    assert res.status_code == 200
    assert "items" in res.json()

def test_get_settings():
    res = client.get("/api/settings")
    assert res.status_code == 200
    assert "hotkey" in res.json()
