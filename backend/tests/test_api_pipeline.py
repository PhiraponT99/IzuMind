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
    monkeypatch.delenv("ENABLE_LOCAL_STT", raising=False)
    monkeypatch.delenv("STT_PROVIDER", raising=False)
    monkeypatch.delenv("STT_MODEL_SIZE", raising=False)
    monkeypatch.delenv("STT_DEVICE", raising=False)
    monkeypatch.delenv("STT_COMPUTE_TYPE", raising=False)
    monkeypatch.delenv("STT_AUDIO_DIR", raising=False)
    monkeypatch.delenv("STT_MAX_DURATION_SECONDS", raising=False)
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
    assert config_body["enable_local_stt"] is False
    assert config_body["stt_provider"] == "faster_whisper"
    assert config_body["stt_model_size"] == "base"
    assert config_body["stt_device"] == "cpu"
    assert config_body["stt_compute_type"] == "int8"
    assert config_body["stt_audio_dir"] == "backend/data/audio"
    assert config_body["stt_max_duration_seconds"] == 900
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


def test_process_youtube_success_uses_mocked_caption_fetcher(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch_youtube_transcript(source_url: str, language: str = "thai") -> dict:
        return {
            "video_id": "abc123XYZ_9",
            "transcript": "00:01 deep work is focused work 00:05 notification makes focus harder",
            "transcript_language": "en",
            "transcript_source": "youtube_caption",
            "is_generated": False,
        }

    monkeypatch.setattr(main_app, "fetch_youtube_transcript", fake_fetch_youtube_transcript)

    response = client.post(
        "/api/videos/process-youtube",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123XYZ_9",
            "language": "english",
            "title": "YouTube Caption Test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["video_id"]
    assert body["title"] == "YouTube Caption Test"
    assert body["source_url"] == "https://www.youtube.com/watch?v=abc123XYZ_9"
    assert body["transcript_source"] == "youtube_caption"
    assert body["youtube_video_id"] == "abc123XYZ_9"
    assert body["transcript_language"] == "en"
    assert body["transcript_is_generated"] is False
    assert body["cleaned_transcript"]
    assert body["chunks"]
    assert body["summary"]
    assert body["summary_provider"] == "rule_based"


def test_process_youtube_transcript_not_found_returns_readable_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch_youtube_transcript(source_url: str, language: str = "thai") -> dict:
        raise main_app.TranscriptNotFoundError(
            "ไม่พบ subtitle/caption สำหรับวิดีโอนี้ กรุณาวาง transcript เองผ่าน /api/videos/process"
        )

    monkeypatch.setattr(main_app, "fetch_youtube_transcript", fake_fetch_youtube_transcript)

    response = client.post(
        "/api/videos/process-youtube",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123XYZ_9",
            "language": "thai",
        },
    )

    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["reason"] == "transcript_not_found"
    assert body["source_url"] == "https://www.youtube.com/watch?v=abc123XYZ_9"
    assert "/api/videos/process" in body["message"]


def test_process_youtube_stt_fallback_disabled_returns_readable_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch_youtube_transcript(source_url: str, language: str = "thai") -> dict:
        raise main_app.TranscriptNotFoundError("caption missing")

    monkeypatch.setattr(main_app, "fetch_youtube_transcript", fake_fetch_youtube_transcript)

    response = client.post(
        "/api/videos/process-youtube",
        json={
            "source_url": "https://www.youtube.com/watch?v=abc123XYZ_9",
            "language": "thai",
            "use_stt_fallback": True,
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert body["reason"] == "local_stt_disabled"
    assert body["source_url"] == "https://www.youtube.com/watch?v=abc123XYZ_9"


def test_process_youtube_stt_fallback_success_uses_mocked_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_dir = _make_test_dir()
    _patch_test_storage(test_dir, monkeypatch)
    monkeypatch.setattr(config, "ENV_FILE", config.PROJECT_ROOT / ".missing-test-env")
    monkeypatch.setenv("SUMMARY_PROVIDER", "rule_based")
    monkeypatch.setenv("ENABLE_LOCAL_STT", "true")
    monkeypatch.setenv("STT_AUDIO_DIR", str(test_dir / "audio"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    def fake_fetch_youtube_transcript(source_url: str, language: str = "thai") -> dict:
        raise main_app.TranscriptNotFoundError("caption missing")

    def fake_download_youtube_audio(
        source_url: str,
        output_dir: str,
        max_duration_seconds: int,
    ) -> dict:
        return {
            "youtube_video_id": "abc123XYZ_9",
            "audio_path": str(test_dir / "audio" / "abc123XYZ_9.m4a"),
            "duration_seconds": 120,
            "audio_source": "youtube_audio",
        }

    def fake_transcribe_audio(audio_path: str, language: str = "thai") -> dict:
        return {
            "transcript": "deep work needs focus and notification should be off",
            "transcript_source": "local_stt",
            "stt_provider": "faster_whisper",
            "stt_model_size": "base",
            "detected_language": "en",
            "duration_seconds": 118.0,
        }

    delete_called_with = None

    def fake_delete_audio_file(file_path: str | None) -> None:
        nonlocal delete_called_with
        delete_called_with = file_path

    monkeypatch.setattr(main_app, "fetch_youtube_transcript", fake_fetch_youtube_transcript)
    monkeypatch.setattr(main_app, "download_youtube_audio", fake_download_youtube_audio)
    monkeypatch.setattr(main_app, "transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(main_app, "delete_audio_file", fake_delete_audio_file)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/videos/process-youtube",
            json={
                "source_url": "https://www.youtube.com/watch?v=abc123XYZ_9",
                "language": "english",
                "title": "YouTube STT Test",
                "use_stt_fallback": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "YouTube STT Test"
        assert body["transcript_source"] == "local_stt"
        assert body["youtube_video_id"] == "abc123XYZ_9"
        assert body["transcript_language"] == "en"
        assert body["transcript_is_generated"] is True
        assert body["stt_provider"] == "faster_whisper"
        assert body["stt_model_size"] == "base"
        assert body["summary_provider"] == "rule_based"
        assert body["chunks"]
        assert delete_called_with == str(test_dir / "audio" / "abc123XYZ_9.m4a")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_process_youtube_stt_fallback_cleanup_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_dir = _make_test_dir()
    _patch_test_storage(test_dir, monkeypatch)
    monkeypatch.setattr(config, "ENV_FILE", config.PROJECT_ROOT / ".missing-test-env")
    monkeypatch.setenv("SUMMARY_PROVIDER", "rule_based")
    monkeypatch.setenv("ENABLE_LOCAL_STT", "true")
    monkeypatch.setenv("STT_AUDIO_DIR", str(test_dir / "audio"))

    def fake_fetch_youtube_transcript(source_url: str, language: str = "thai") -> dict:
        raise main_app.TranscriptNotFoundError("caption missing")

    def fake_download_youtube_audio(
        source_url: str,
        output_dir: str,
        max_duration_seconds: int,
    ) -> dict:
        return {
            "youtube_video_id": "abc123XYZ_9",
            "audio_path": str(test_dir / "audio" / "abc123XYZ_9.m4a"),
            "duration_seconds": 120,
            "audio_source": "youtube_audio",
        }

    def fake_transcribe_audio_fail(audio_path: str, language: str = "thai") -> dict:
        raise main_app.LocalSTTError("transcription error")

    delete_called_with = None

    def fake_delete_audio_file(file_path: str | None) -> None:
        nonlocal delete_called_with
        delete_called_with = file_path

    monkeypatch.setattr(main_app, "fetch_youtube_transcript", fake_fetch_youtube_transcript)
    monkeypatch.setattr(main_app, "download_youtube_audio", fake_download_youtube_audio)
    monkeypatch.setattr(main_app, "transcribe_audio", fake_transcribe_audio_fail)
    monkeypatch.setattr(main_app, "delete_audio_file", fake_delete_audio_file)

    try:
        client = TestClient(app)
        response = client.post(
            "/api/videos/process-youtube",
            json={
                "source_url": "https://www.youtube.com/watch?v=abc123XYZ_9",
                "language": "english",
                "title": "YouTube STT Test",
                "use_stt_fallback": True,
            },
        )

        assert response.status_code == 422
        body = response.json()
        assert body["reason"] == "local_stt_failed"
        assert delete_called_with == str(test_dir / "audio" / "abc123XYZ_9.m4a")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_stt_smoke_test_returns_config_only(client: TestClient) -> None:
    response = client.get("/api/stt/smoke-test")

    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "config"
    assert body["enable_local_stt"] is False
    assert body["stt_provider"] == "faster_whisper"
    assert body["stt_model_size"] == "base"
    assert body["stt_device"] == "cpu"
    assert body["stt_compute_type"] == "int8"
    assert "yt_dlp_import_ok" in body
    assert "faster_whisper_import_ok" in body


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
