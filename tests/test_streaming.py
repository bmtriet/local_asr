import pytest
from fastapi.testclient import TestClient
from web.api import app

def test_settings_streaming_transcription():
    client = TestClient(app)
    # 1. Check get settings returns streaming_transcription_enabled field
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "streaming_transcription_enabled" in data

    # 2. Toggle streaming_transcription_enabled to true
    res = client.post("/api/settings", json={"streaming_transcription_enabled": True})
    assert res.status_code == 200
    assert res.json()["settings"]["streaming_transcription_enabled"] is True

    # 3. Toggle back to false
    res = client.post("/api/settings", json={"streaming_transcription_enabled": False})
    assert res.status_code == 200
    assert res.json()["settings"]["streaming_transcription_enabled"] is False

def test_websocket_streaming_connect():
    client = TestClient(app)
    with client.websocket_connect("/api/ws/streaming-transcribe") as websocket:
        # Send reset message
        websocket.send_text('{"event": "reset"}')
        data = websocket.receive_json()
        assert data == {"event": "reset_ack"}

        # Send empty finish message
        websocket.send_text('{"event": "finish"}')
        data = websocket.receive_json()
        assert data.get("event") == "final_text"
