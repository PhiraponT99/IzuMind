from pathlib import Path
from uuid import uuid4
import shutil

import pytest
from fastapi.testclient import TestClient

import app.config as config
import app.main as main_app
import app.storage.video_store as video_store
from app.main import app

THAI_DEEP_WORK_REQUEST = {
    "title": "Deep Work Test",
    "source_url": "https://youtube.com/test",
    "language": "thai",
    "transcript": (
        "00:01 วันนี้เราจะพูดถึง deep work "
        "00:05 deep work คือการทำงานแบบมีสมาธิลึกและไม่ถูกรบกวน "
        "00:10 ปัญหาของยุคนี้คือมือถือ notification และ social media ทำให้เราหลุดโฟกัสบ่อย "
        "00:15 เมื่อเราเช็กมือถือ สมองจะได้รับ dopamine สั้น ๆ ทำให้เราติดการสลับความสนใจ "
        "00:20 ถ้าอยากทำงานลึก เราควรปิด notification วางมือถือให้ไกล "
        "และกำหนดช่วงเวลาทำงานที่ชัดเจน"
    ),
}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    test_dir = _make_test_dir()
    _patch_test_storage(test_dir, monkeypatch)
    monkeypatch.setattr(config, "ENV_FILE", config.PROJECT_ROOT / ".missing-test-env")
    monkeypatch.setenv("SUMMARY_PROVIDER", "rule_based")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    try:
        yield TestClient(app)
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def _make_test_dir() -> Path:
    test_dir = Path(".test_tmp") / str(uuid4())
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def _patch_test_storage(test_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(video_store, "DATA_DIR", test_dir)
    monkeypatch.setattr(video_store, "VIDEOS_FILE", test_dir / "videos.json")
    monkeypatch.setattr(main_app, "save_video", video_store.save_video)
    monkeypatch.setattr(main_app, "get_video", video_store.get_video)
    monkeypatch.setattr(main_app, "list_videos", video_store.list_videos)


def test_process_ask_and_markdown_export_pipeline(client: TestClient) -> None:
    config_response = client.get("/api/config")
    assert config_response.status_code == 200
    config_body = config_response.json()
    assert config_body["summary_provider"] == "rule_based"
    assert config_body["openai_api_key_present"] is False
    assert config_body["openai_model_present"] is False
    assert config_body["openai_config_valid"] is False
    assert config_body["ollama_base_url"] == "http://localhost:11434"
    assert config_body["ollama_model"] is None
    assert config_body["ollama_base_url_present"] is True
    assert config_body["ollama_model_present"] is False
    assert config_body["ollama_config_valid"] is False
    assert config_body["env_file_exists"] is False
    assert config_body["env_file_path"].endswith(".missing-test-env")
    assert "OPENAI_API_KEY" not in config_response.text
    assert "your_real_api_key" not in config_response.text

    process_response = client.post("/api/videos/process", json=THAI_DEEP_WORK_REQUEST)

    assert process_response.status_code == 200
    process_body = process_response.json()
    assert process_body["video_id"]
    assert process_body["cleaned_transcript"]
    assert process_body["chunks"]
    assert process_body["summary"]
    assert process_body["summary_provider"] == "rule_based"
    assert process_body["summary_fallback_used"] is False
    assert "00:01" not in process_body["cleaned_transcript"]
    assert "00:20" not in process_body["cleaned_transcript"]
    assert any("ปิด notification" in item for item in process_body["summary"]["action_items"])
    assert any("วางมือถือ" in item for item in process_body["summary"]["action_items"])
    assert any("กำหนดช่วงเวลา" in item for item in process_body["summary"]["action_items"])

    video_id = process_body["video_id"]
    ask_response = client.post(
        f"/api/videos/{video_id}/ask",
        json={"question": "วิดีโอนี้พูดถึงมือถือกับ deep work ยังไง"},
    )

    assert ask_response.status_code == 200
    ask_body = ask_response.json()
    assert ask_body["answer"]
    assert ask_body["related_chunks"]

    markdown_response = client.get(f"/api/videos/{video_id}/export/markdown")

    assert markdown_response.status_code == 200
    markdown_text = markdown_response.text
    assert "# Deep Work Test" in markdown_text
    assert "## TL;DR" in markdown_text
    assert "## Main Ideas" in markdown_text
    assert "## Key Takeaways" in markdown_text
    assert "## Action Items" in markdown_text
    assert "## Questions to Think" in markdown_text
    assert "## Transcript Chunks" in markdown_text


def test_openai_smoke_test_without_config_returns_safe_config_failure(
    client: TestClient,
) -> None:
    response = client.get("/api/llm/openai/smoke-test")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["stage"] == "config"
    assert body["message"] == "OpenAI config is invalid"
    assert body["openai_api_key_present"] is False
    assert body["openai_model"] is None
    assert "OPENAI_API_KEY" not in response.text
    assert "your_real_api_key" not in response.text


def test_ollama_smoke_test_without_model_returns_safe_config_failure(
    client: TestClient,
) -> None:
    response = client.get("/api/llm/ollama/smoke-test")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["stage"] == "config"
    assert body["message"] == "Ollama config is invalid"
    assert body["ollama_base_url"] == "http://localhost:11434"
    assert body["ollama_model"] is None


def test_openai_provider_without_config_returns_fallback_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_dir = _make_test_dir()
    _patch_test_storage(test_dir, monkeypatch)
    monkeypatch.setattr(config, "ENV_FILE", config.PROJECT_ROOT / ".missing-test-env")
    monkeypatch.setenv("SUMMARY_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    try:
        client = TestClient(app)
        config_response = client.get("/api/config")
        assert config_response.status_code == 200
        config_body = config_response.json()
        assert config_body["summary_provider"] == "openai"
        assert config_body["openai_api_key_present"] is False
        assert config_body["openai_model_present"] is False
        assert config_body["openai_config_valid"] is False
        assert config_body["env_file_exists"] is False

        response = client.post("/api/videos/process", json=THAI_DEEP_WORK_REQUEST)

        assert response.status_code == 200
        body = response.json()
        assert body["summary_provider"] == "rule_based"
        assert body["summary_fallback_used"] is True
        assert body["summary"]
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_ollama_provider_without_model_returns_fallback_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_dir = _make_test_dir()
    _patch_test_storage(test_dir, monkeypatch)
    monkeypatch.setattr(config, "ENV_FILE", config.PROJECT_ROOT / ".missing-test-env")
    monkeypatch.setenv("SUMMARY_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    try:
        client = TestClient(app)
        config_response = client.get("/api/config")
        assert config_response.status_code == 200
        config_body = config_response.json()
        assert config_body["summary_provider"] == "ollama"
        assert config_body["ollama_base_url_present"] is True
        assert config_body["ollama_model_present"] is False
        assert config_body["ollama_config_valid"] is False

        response = client.post("/api/videos/process", json=THAI_DEEP_WORK_REQUEST)

        assert response.status_code == 200
        body = response.json()
        assert body["summary_provider"] == "rule_based"
        assert body["summary_fallback_used"] is True
        assert body["summary"]
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
