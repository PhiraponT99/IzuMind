import json
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
JOBS_FILE = DATA_DIR / "jobs.json"


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not JOBS_FILE.exists() or JOBS_FILE.stat().st_size == 0:
        _write_jobs([])


def _write_jobs(jobs: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with JOBS_FILE.open("w", encoding="utf-8") as file:
        json.dump(jobs, file, ensure_ascii=False, indent=2)


def create_job(source_url: str, title: str | None, language: str, use_stt_fallback: bool) -> dict:
    _ensure_store()
    now_iso = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": str(uuid4()),
        "status": "queued",
        "stage": "queued",
        "progress_percent": 0,
        "message": "Long video processing has been queued. Real background processing will be implemented later.",
        "source_url": source_url,
        "title": title,
        "language": language,
        "use_stt_fallback": use_stt_fallback,
        "video_id": None,
        "error_message": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    jobs = []
    try:
        with JOBS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, list):
                jobs = [item for item in data if isinstance(item, dict)]
    except (json.JSONDecodeError, OSError):
        pass

    jobs.append(job)
    _write_jobs(jobs)
    return job


def get_job(job_id: str) -> dict | None:
    _ensure_store()
    try:
        with JOBS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(data, list):
        return None

    for job in data:
        if isinstance(job, dict) and job.get("job_id") == job_id:
            return job
    return None


def list_jobs(limit: int = 50) -> list[dict]:
    _ensure_store()
    try:
        with JOBS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        _write_jobs([])
        return []

    if not isinstance(data, list):
        _write_jobs([])
        return []

    valid_jobs = [item for item in data if isinstance(item, dict)]
    # Return recent jobs (most recently created/appended first)
    return valid_jobs[::-1][:limit]


def update_job(job_id: str, **updates) -> dict:
    _ensure_store()
    try:
        with JOBS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        data = []

    if not isinstance(data, list):
        data = []

    updated_job = None
    now_iso = datetime.now(timezone.utc).isoformat()
    for job in data:
        if isinstance(job, dict) and job.get("job_id") == job_id:
            job.update(updates)
            job["updated_at"] = now_iso
            updated_job = job
            break

    if updated_job is None:
        raise ValueError(f"Job with id {job_id} not found")

    _write_jobs(data)
    return updated_job


def fail_job(job_id: str, error_message: str) -> dict:
    return update_job(
        job_id,
        status="failed",
        stage="failed",
        error_message=error_message,
        message=f"Failed: {error_message}"
    )


def complete_job(job_id: str, video_id: str, message: str = "completed") -> dict:
    return update_job(
        job_id,
        status="completed",
        stage="completed",
        video_id=video_id,
        progress_percent=100,
        message=message
    )
