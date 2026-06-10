import logging
from pathlib import Path
from typing import Any

from app.services.youtube_utils import extract_youtube_video_id

LOGGER = logging.getLogger(__name__)


class AudioDownloadError(Exception):
    """Raised when YouTube audio cannot be downloaded safely."""


def download_youtube_audio(
    source_url: str,
    output_dir: str,
    max_duration_seconds: int,
) -> dict:
    video_id = extract_youtube_video_id(source_url)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise AudioDownloadError("yt-dlp is not installed. Run pip install -r requirements.txt.") from exc

    options = {
        "format": "bestaudio/best",
        "outtmpl": str(output_path / f"{video_id}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            }
        ],
    }

    try:
        with YoutubeDL({**options, "skip_download": True}) as ydl:
            info = ydl.extract_info(source_url, download=False)
        duration_seconds = _duration_seconds(info)
        if duration_seconds and duration_seconds > max_duration_seconds:
            raise AudioDownloadError(
                f"Video duration {duration_seconds} seconds exceeds STT limit of {max_duration_seconds} seconds."
            )

        with YoutubeDL(options) as ydl:
            ydl.download([source_url])
    except AudioDownloadError:
        raise
    except Exception as exc:
        raise AudioDownloadError(f"Could not download YouTube audio: {_safe_message(exc)}") from exc

    audio_path = _find_downloaded_audio(output_path, video_id)
    if audio_path is None:
        raise AudioDownloadError("Audio download finished but no output audio file was found.")

    return {
        "youtube_video_id": video_id,
        "audio_path": str(audio_path),
        "duration_seconds": duration_seconds,
        "audio_source": "youtube_audio",
    }


def _duration_seconds(info: dict[str, Any] | None) -> int | None:
    if not info:
        return None

    duration = info.get("duration")
    if duration is None:
        return None

    try:
        return int(duration)
    except (TypeError, ValueError):
        return None


def _find_downloaded_audio(output_dir: Path, video_id: str) -> Path | None:
    for extension in ("m4a", "mp3", "wav", "webm", "opus"):
        candidate = output_dir / f"{video_id}.{extension}"
        if candidate.exists():
            return candidate

    matches = sorted(output_dir.glob(f"{video_id}.*"))
    return matches[0] if matches else None


def _safe_message(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    if len(message) <= 180:
        return message
    return f"{message[:177].rstrip()}..."


def delete_audio_file(file_path: str | None) -> None:
    if not file_path:
        return
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
    except Exception as exc:
        LOGGER.warning("Could not clean up temporary audio file %s: %s", file_path, exc)
