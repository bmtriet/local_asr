import pytest
import io
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from web.api import app, settings

@pytest.fixture
def client():
    return TestClient(app)

def test_export_vocabulary_default_and_profile(client):
    # Export default
    res = client.get("/api/vocabulary/export")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    assert "vocabulary_default.json" in res.headers.get("content-disposition", "")

    # Export specific profile
    res_prof = client.get("/api/vocabulary/export?profile_id=default")
    assert res_prof.status_code == 200
    assert len(res_prof.content) > 0

def test_export_lora_adapter_not_found(client):
    # Test exporting when adapter has not been trained yet
    res = client.get("/api/train/export?profile_id=non_existent_profile_xyz")
    assert res.status_code == 404
    assert "No trained LoRA adapter found" in res.json()["detail"]

def test_export_lora_adapter_success(client, tmp_path):
    # Mock a trained adapter folder
    test_adapter_dir = settings.ADAPTERS_DIR / "test_user_export"
    test_adapter_dir.mkdir(parents=True, exist_ok=True)
    try:
        (test_adapter_dir / "adapter_config.json").write_text('{"base_model": "Qwen3-ASR"}')
        (test_adapter_dir / "adapter_model.safetensors").write_bytes(b"dummy_weights_data")

        res = client.get("/api/train/export?profile_id=test_user_export")
        assert res.status_code == 200
        assert "application/zip" in res.headers["content-type"]
        assert "lora_adapter_test_user_export.zip" in res.headers.get("content-disposition", "")

        # Verify zip contents
        zip_buf = io.BytesIO(res.content)
        with zipfile.ZipFile(zip_buf, "r") as z:
            namelist = z.namelist()
            assert "adapter_config.json" in namelist
            assert "adapter_model.safetensors" in namelist
    finally:
        import shutil
        if test_adapter_dir.exists():
            shutil.rmtree(test_adapter_dir)

def test_export_profile_bundle(client):
    # Export bundle for default profile
    res = client.get("/api/profiles/export-bundle?profile_id=default&include_vocab=true&include_lora=true")
    assert res.status_code == 200
    assert "application/zip" in res.headers["content-type"]
    assert "local_asr_profile_default.zip" in res.headers.get("content-disposition", "")

    zip_buf = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_buf, "r") as z:
        namelist = z.namelist()
        assert "vocabulary.json" in namelist
        assert "profile_manifest.json" in namelist

def test_inspect_and_import_profile_bundle(client, tmp_path):
    # 1. Export a real bundle
    res_export = client.get("/api/profiles/export-bundle?profile_id=default&include_vocab=true&include_lora=false")
    assert res_export.status_code == 200
    zip_bytes = res_export.content

    # 2. Inspect bundle
    files = {"file": ("test_bundle.zip", zip_bytes, "application/zip")}
    res_inspect = client.post("/api/profiles/inspect-bundle", files=files)
    assert res_inspect.status_code == 200
    inspect_data = res_inspect.json()
    assert inspect_data["valid"] is True
    assert inspect_data["has_vocabulary"] is True

    # 3. Import bundle under a new profile ID
    import_files = {"file": ("test_bundle.zip", zip_bytes, "application/zip")}
    import_data = {
        "target_profile_id": "test_imported_unit",
        "target_profile_name": "Test Imported Unit",
        "target_profile_desc": "Unit Test Imported Description",
        "overwrite": "true",
        "set_active": "false"
    }
    res_import = client.post("/api/profiles/import-bundle", files=import_files, data=import_data)
    assert res_import.status_code == 200
    res_json = res_import.json()
    assert res_json["status"] == "success"
    assert res_json["profile_id"] == "test_imported_unit"

    # Verify profile now exists
    res_profiles = client.get("/api/profiles")
    assert any(p["id"] == "test_imported_unit" for p in res_profiles.json()["profiles"])
