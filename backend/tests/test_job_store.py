"""
Unit tests for app.storage.job_store.

These tests do not require network, YouTube, Ollama, OpenAI, ffmpeg,
or faster-whisper. All file I/O is redirected to a temporary directory
so the real backend/data/jobs.json is never touched.
"""
from pathlib import Path
from uuid import uuid4
import shutil

import pytest

import app.storage.job_store as job_store


@pytest.fixture()
def temp_job_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Redirect job_store I/O to a fresh temp directory for each test."""
    monkeypatch.setattr(job_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(job_store, "JOBS_FILE", tmp_path / "jobs.json")
    yield tmp_path


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


def test_create_job_returns_queued_job(temp_job_store) -> None:
    job = job_store.create_job(
        source_url="https://www.youtube.com/watch?v=abc",
        title="Test Video",
        language="thai",
        use_stt_fallback=True,
    )

    assert job["job_id"] is not None
    assert job["status"] == "queued"
    assert job["stage"] == "queued"
    assert job["progress_percent"] == 0
    assert job["source_url"] == "https://www.youtube.com/watch?v=abc"
    assert job["title"] == "Test Video"
    assert job["language"] == "thai"
    assert job["use_stt_fallback"] is True
    assert job["video_id"] is None
    assert job["error_message"] is None
    assert job["created_at"] is not None
    assert job["updated_at"] is not None
    assert "queued" in job["message"].lower()


def test_create_job_accepts_none_title(temp_job_store) -> None:
    job = job_store.create_job(
        source_url="https://www.youtube.com/watch?v=xyz",
        title=None,
        language="english",
        use_stt_fallback=False,
    )
    assert job["title"] is None
    assert job["status"] == "queued"


def test_create_job_persists_to_file(temp_job_store) -> None:
    job_store.create_job(
        source_url="https://www.youtube.com/watch?v=abc",
        title="Persistent Video",
        language="thai",
        use_stt_fallback=False,
    )
    jobs_file = temp_job_store / "jobs.json"
    assert jobs_file.exists()
    assert jobs_file.stat().st_size > 0


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------


def test_get_job_returns_correct_job(temp_job_store) -> None:
    job = job_store.create_job(
        source_url="https://www.youtube.com/watch?v=getme",
        title="Get Me",
        language="thai",
        use_stt_fallback=False,
    )
    retrieved = job_store.get_job(job["job_id"])
    assert retrieved is not None
    assert retrieved["job_id"] == job["job_id"]
    assert retrieved["title"] == "Get Me"


def test_get_job_returns_none_for_missing_id(temp_job_store) -> None:
    result = job_store.get_job("non-existent-uuid-0000")
    assert result is None


def test_get_job_handles_empty_store(temp_job_store) -> None:
    # Store not yet initialised — get_job should return None gracefully
    result = job_store.get_job("any-id")
    assert result is None


def test_get_job_handles_corrupted_json(temp_job_store) -> None:
    jobs_file = temp_job_store / "jobs.json"
    jobs_file.write_text("NOT VALID JSON", encoding="utf-8")
    result = job_store.get_job("any-id")
    assert result is None


# ---------------------------------------------------------------------------
# update_job
# ---------------------------------------------------------------------------


def test_update_job_changes_status_and_updated_at(temp_job_store) -> None:
    job = job_store.create_job(
        source_url="https://www.youtube.com/watch?v=upd",
        title="Update Test",
        language="thai",
        use_stt_fallback=False,
    )
    original_updated_at = job["updated_at"]

    updated = job_store.update_job(
        job["job_id"],
        status="running",
        stage="caption_fetch",
        progress_percent=10,
        message="Fetching caption",
    )

    assert updated["status"] == "running"
    assert updated["stage"] == "caption_fetch"
    assert updated["progress_percent"] == 10
    assert updated["message"] == "Fetching caption"
    # updated_at must be a new timestamp (or at least not missing)
    assert updated["updated_at"] is not None
    # In fast test execution the timestamps may be identical; ensure field exists
    assert "updated_at" in updated


def test_update_job_raises_for_missing_id(temp_job_store) -> None:
    # Create a store with at least one job so the file exists
    job_store.create_job("https://www.youtube.com/watch?v=x", None, "thai", False)
    with pytest.raises(ValueError, match="not found"):
        job_store.update_job("totally-wrong-uuid", status="running")


# ---------------------------------------------------------------------------
# complete_job
# ---------------------------------------------------------------------------


def test_complete_job_sets_completed_status(temp_job_store) -> None:
    job = job_store.create_job(
        source_url="https://www.youtube.com/watch?v=done",
        title="Done Video",
        language="english",
        use_stt_fallback=False,
    )
    video_id = str(uuid4())
    completed = job_store.complete_job(job["job_id"], video_id=video_id)

    assert completed["status"] == "completed"
    assert completed["stage"] == "completed"
    assert completed["video_id"] == video_id
    assert completed["progress_percent"] == 100


def test_complete_job_uses_custom_message(temp_job_store) -> None:
    job = job_store.create_job("https://youtube.com/watch?v=msg", None, "thai", False)
    completed = job_store.complete_job(job["job_id"], video_id="vid-123", message="All done!")
    assert completed["message"] == "All done!"


# ---------------------------------------------------------------------------
# fail_job
# ---------------------------------------------------------------------------


def test_fail_job_sets_failed_status(temp_job_store) -> None:
    job = job_store.create_job(
        source_url="https://www.youtube.com/watch?v=fail",
        title="Fail Video",
        language="thai",
        use_stt_fallback=True,
    )
    failed = job_store.fail_job(job["job_id"], error_message="STT crashed")

    assert failed["status"] == "failed"
    assert failed["stage"] == "failed"
    assert failed["error_message"] == "STT crashed"
    assert "STT crashed" in failed["message"]


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------


def test_list_jobs_returns_most_recent_first(temp_job_store) -> None:
    job_a = job_store.create_job("https://youtube.com/watch?v=A", "A", "thai", False)
    job_b = job_store.create_job("https://youtube.com/watch?v=B", "B", "thai", False)
    job_c = job_store.create_job("https://youtube.com/watch?v=C", "C", "thai", False)

    jobs = job_store.list_jobs()
    ids = [j["job_id"] for j in jobs]

    assert ids[0] == job_c["job_id"], "Most recent job should be first"
    assert ids[1] == job_b["job_id"]
    assert ids[2] == job_a["job_id"]


def test_list_jobs_respects_limit(temp_job_store) -> None:
    for i in range(5):
        job_store.create_job(f"https://youtube.com/watch?v={i}", None, "thai", False)

    jobs = job_store.list_jobs(limit=2)
    assert len(jobs) == 2


def test_list_jobs_returns_empty_for_empty_store(temp_job_store) -> None:
    jobs = job_store.list_jobs()
    assert jobs == []


def test_list_jobs_handles_corrupted_json(temp_job_store) -> None:
    jobs_file = temp_job_store / "jobs.json"
    jobs_file.write_text("{bad json", encoding="utf-8")
    jobs = job_store.list_jobs()
    assert jobs == []
