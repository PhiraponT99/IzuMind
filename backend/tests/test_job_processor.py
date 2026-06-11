"""
Unit tests for app.services.job_processor.process_youtube_job.

All external calls (YouTube, STT, Ollama, OpenAI, ffmpeg, network) are
replaced by fakes via monkeypatch.  No real I/O or network is needed.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import shutil

import pytest

import app.storage.job_store as job_store
import app.services.job_processor as job_processor_module
from app.services.job_processor import process_youtube_job


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Redirect job_store I/O to a fresh temp directory."""
    monkeypatch.setattr(job_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(job_store, "JOBS_FILE", tmp_path / "jobs.json")

    # Also redirect video_store so save_video does not touch real files.
    import app.storage.video_store as video_store
    monkeypatch.setattr(video_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(video_store, "VIDEOS_FILE", tmp_path / "videos.json")
    yield tmp_path


def _make_job(
    temp_store,
    source_url: str = "https://www.youtube.com/watch?v=test123",
    title: str | None = "Test Video",
    language: str = "thai",
    use_stt_fallback: bool = False,
) -> dict:
    return job_store.create_job(
        source_url=source_url,
        title=title,
        language=language,
        use_stt_fallback=use_stt_fallback,
    )


# ---------------------------------------------------------------------------
# Helper: build a minimal fake settings object
# ---------------------------------------------------------------------------


class _FakeSettings:
    is_local_stt_enabled = False
    stt_audio_dir = "backend/data/audio"
    stt_max_duration_seconds = 900


class _FakeSettingsSTTEnabled:
    is_local_stt_enabled = True
    stt_audio_dir = "backend/data/audio"
    stt_max_duration_seconds = 900


# ---------------------------------------------------------------------------
# 1. Caption success path
# ---------------------------------------------------------------------------


def test_process_youtube_job_caption_success(
    temp_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When YouTube captions are available the job should complete."""
    job = _make_job(temp_store)
    job_id = job["job_id"]

    # Fake caption fetcher
    def fake_fetch(source_url, language="thai"):
        return {
            "video_id": "cap123",
            "transcript": "deep work is focused work without distraction",
            "transcript_language": "en",
            "transcript_source": "youtube_caption",
            "is_generated": False,
        }

    monkeypatch.setattr(job_processor_module, "fetch_youtube_transcript", fake_fetch, raising=False)

    # Patch the lazy imports inside process_youtube_job / _run_pipeline
    import app.services.youtube_caption_fetcher as caption_mod
    monkeypatch.setattr(caption_mod, "fetch_youtube_transcript", fake_fetch)

    process_youtube_job(job_id)

    result = job_store.get_job(job_id)
    assert result is not None
    assert result["status"] == "completed"
    assert result["stage"] == "completed"
    assert result["progress_percent"] == 100
    assert result["video_id"] is not None
    assert result["error_message"] is None


# ---------------------------------------------------------------------------
# 2. Caption not found + no STT fallback
# ---------------------------------------------------------------------------


def test_process_youtube_job_caption_not_found_no_stt(
    temp_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Job should fail with transcript_not_found when captions are missing and STT is off."""
    job = _make_job(temp_store, use_stt_fallback=False)
    job_id = job["job_id"]

    from app.services.youtube_caption_fetcher import TranscriptNotFoundError
    import app.services.youtube_caption_fetcher as caption_mod

    def fake_fetch(source_url, language="thai"):
        raise TranscriptNotFoundError("no captions")

    monkeypatch.setattr(caption_mod, "fetch_youtube_transcript", fake_fetch)

    process_youtube_job(job_id)

    result = job_store.get_job(job_id)
    assert result is not None
    assert result["status"] == "failed"
    assert result["stage"] == "failed"
    assert result["error_message"] is not None
    assert "transcript_not_found" in result["error_message"] or "subtitle" in result["error_message"]


# ---------------------------------------------------------------------------
# 3. Caption not found + STT requested but local STT disabled
# ---------------------------------------------------------------------------


def test_process_youtube_job_caption_not_found_stt_disabled(
    temp_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Job should fail with local_stt_disabled when STT is requested but not enabled."""
    job = _make_job(temp_store, use_stt_fallback=True)
    job_id = job["job_id"]

    from app.services.youtube_caption_fetcher import TranscriptNotFoundError
    import app.services.youtube_caption_fetcher as caption_mod
    import app.config as config_mod

    def fake_fetch(source_url, language="thai"):
        raise TranscriptNotFoundError("no captions")

    monkeypatch.setattr(caption_mod, "fetch_youtube_transcript", fake_fetch)
    monkeypatch.setattr(config_mod, "get_settings", lambda: _FakeSettings())

    process_youtube_job(job_id)

    result = job_store.get_job(job_id)
    assert result is not None
    assert result["status"] == "failed"
    assert result["error_message"] is not None
    assert "local STT" in result["error_message"] or "stt" in result["error_message"].lower()


# ---------------------------------------------------------------------------
# 4. STT success path
# ---------------------------------------------------------------------------


def test_process_youtube_job_stt_success(
    temp_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When captions are missing and STT is enabled, pipeline should complete via STT."""
    job = _make_job(temp_store, use_stt_fallback=True)
    job_id = job["job_id"]

    from app.services.youtube_caption_fetcher import TranscriptNotFoundError
    import app.services.youtube_caption_fetcher as caption_mod
    import app.services.youtube_audio_downloader as audio_mod
    import app.services.local_stt as stt_mod
    import app.config as config_mod

    def fake_fetch(source_url, language="thai"):
        raise TranscriptNotFoundError("no captions")

    deleted_paths: list[str] = []

    def fake_download(source_url, output_dir, max_duration_seconds):
        return {
            "youtube_video_id": "stt123",
            "audio_path": "/fake/path/stt123.m4a",
            "duration_seconds": 120,
            "audio_source": "youtube_audio",
        }

    def fake_transcribe(audio_path, language="thai"):
        return {
            "transcript": "ทำงานอย่างมีสมาธิ ไม่ถูกรบกวน",
            "transcript_source": "local_stt",
            "stt_provider": "faster_whisper",
            "stt_model_size": "base",
            "detected_language": "th",
            "duration_seconds": 118.0,
        }

    def fake_delete(file_path):
        if file_path:
            deleted_paths.append(file_path)

    monkeypatch.setattr(caption_mod, "fetch_youtube_transcript", fake_fetch)
    monkeypatch.setattr(audio_mod, "download_youtube_audio", fake_download)
    monkeypatch.setattr(stt_mod, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(audio_mod, "delete_audio_file", fake_delete)
    monkeypatch.setattr(config_mod, "get_settings", lambda: _FakeSettingsSTTEnabled())

    process_youtube_job(job_id)

    result = job_store.get_job(job_id)
    assert result is not None
    assert result["status"] == "completed"
    assert result["stage"] == "completed"
    assert result["progress_percent"] == 100
    assert result["video_id"] is not None
    # Audio should have been cleaned up
    assert "/fake/path/stt123.m4a" in deleted_paths


# ---------------------------------------------------------------------------
# 5. STT path — audio download fails
# ---------------------------------------------------------------------------


def test_process_youtube_job_audio_download_fails(
    temp_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If audio download raises AudioDownloadError the job should fail cleanly."""
    job = _make_job(temp_store, use_stt_fallback=True)
    job_id = job["job_id"]

    from app.services.youtube_caption_fetcher import TranscriptNotFoundError
    from app.services.youtube_audio_downloader import AudioDownloadError
    import app.services.youtube_caption_fetcher as caption_mod
    import app.services.youtube_audio_downloader as audio_mod
    import app.config as config_mod

    def fake_fetch(source_url, language="thai"):
        raise TranscriptNotFoundError("no captions")

    def fake_download(source_url, output_dir, max_duration_seconds):
        raise AudioDownloadError("network error")

    monkeypatch.setattr(caption_mod, "fetch_youtube_transcript", fake_fetch)
    monkeypatch.setattr(audio_mod, "download_youtube_audio", fake_download)
    monkeypatch.setattr(config_mod, "get_settings", lambda: _FakeSettingsSTTEnabled())

    process_youtube_job(job_id)

    result = job_store.get_job(job_id)
    assert result is not None
    assert result["status"] == "failed"
    assert result["error_message"] is not None


# ---------------------------------------------------------------------------
# 6. STT path — transcription fails; audio still cleaned up
# ---------------------------------------------------------------------------


def test_process_youtube_job_transcription_fails_audio_cleaned(
    temp_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even when transcription fails the audio file should be deleted."""
    job = _make_job(temp_store, use_stt_fallback=True)
    job_id = job["job_id"]

    from app.services.youtube_caption_fetcher import TranscriptNotFoundError
    from app.services.local_stt import LocalSTTError
    import app.services.youtube_caption_fetcher as caption_mod
    import app.services.youtube_audio_downloader as audio_mod
    import app.services.local_stt as stt_mod
    import app.config as config_mod

    deleted_paths: list[str] = []

    def fake_fetch(source_url, language="thai"):
        raise TranscriptNotFoundError("no captions")

    def fake_download(source_url, output_dir, max_duration_seconds):
        return {
            "youtube_video_id": "fail123",
            "audio_path": "/fake/fail123.m4a",
            "duration_seconds": 60,
            "audio_source": "youtube_audio",
        }

    def fake_transcribe(audio_path, language="thai"):
        raise LocalSTTError("model crashed")

    def fake_delete(file_path):
        if file_path:
            deleted_paths.append(file_path)

    monkeypatch.setattr(caption_mod, "fetch_youtube_transcript", fake_fetch)
    monkeypatch.setattr(audio_mod, "download_youtube_audio", fake_download)
    monkeypatch.setattr(stt_mod, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(audio_mod, "delete_audio_file", fake_delete)
    monkeypatch.setattr(config_mod, "get_settings", lambda: _FakeSettingsSTTEnabled())

    process_youtube_job(job_id)

    result = job_store.get_job(job_id)
    assert result is not None
    assert result["status"] == "failed"
    # Cleanup must have run even though transcription failed
    assert "/fake/fail123.m4a" in deleted_paths


# ---------------------------------------------------------------------------
# 7. Missing job_id — should return without crashing
# ---------------------------------------------------------------------------


def test_process_youtube_job_missing_job_id(
    temp_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """process_youtube_job should return silently when the job_id doesn't exist."""
    # Should not raise
    process_youtube_job("completely-unknown-uuid")
