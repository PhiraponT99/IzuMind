import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
VIDEOS_FILE = DATA_DIR / "videos.json"


def save_video(video: dict) -> None:
    videos = list_videos()
    videos.append(video)
    _write_videos(videos)


def get_video(video_id: str) -> dict | None:
    for video in list_videos():
        if video.get("video_id") == video_id:
            return video

    return None


def list_videos() -> list[dict]:
    _ensure_store()
    try:
        with VIDEOS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        _write_videos([])
        return []

    if not isinstance(data, list):
        _write_videos([])
        return []

    return [item for item in data if isinstance(item, dict)]


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not VIDEOS_FILE.exists() or VIDEOS_FILE.stat().st_size == 0:
        _write_videos([])


def _write_videos(videos: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with VIDEOS_FILE.open("w", encoding="utf-8") as file:
        json.dump(videos, file, ensure_ascii=False, indent=2)
