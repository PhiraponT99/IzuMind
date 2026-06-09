from typing import Any

from app.config import get_settings


class LocalSTTError(Exception):
    """Raised when local speech-to-text cannot transcribe audio safely."""


def transcribe_audio(audio_path: str, language: str = "thai") -> dict:
    settings = get_settings()
    if settings.stt_provider != "faster_whisper":
        raise LocalSTTError(f"Unsupported STT provider: {settings.stt_provider}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise LocalSTTError("faster-whisper is not installed. Run pip install -r requirements.txt.") from exc

    try:
        model = WhisperModel(
            settings.stt_model_size,
            device=settings.stt_device,
            compute_type=settings.stt_compute_type,
        )
        segments, info = model.transcribe(
            audio_path,
            language=_language_code(language),
        )
        segment_list = list(segments)
    except Exception as exc:
        raise LocalSTTError(f"Could not transcribe audio locally: {_safe_message(exc)}") from exc

    transcript = " ".join(_segment_text(segment) for segment in segment_list)
    transcript = " ".join(transcript.split())
    if not transcript:
        raise LocalSTTError("Local STT produced an empty transcript.")

    return {
        "transcript": transcript,
        "transcript_source": "local_stt",
        "stt_provider": "faster_whisper",
        "stt_model_size": settings.stt_model_size,
        "detected_language": str(getattr(info, "language", _language_code(language) or "")),
        "duration_seconds": _duration_seconds(info),
    }


def _language_code(language: str) -> str | None:
    normalized = language.lower().strip()
    if normalized == "thai":
        return "th"
    if normalized == "english":
        return "en"
    return None


def _segment_text(segment: Any) -> str:
    if isinstance(segment, dict):
        return str(segment.get("text", ""))

    return str(getattr(segment, "text", ""))


def _duration_seconds(info: Any) -> float | None:
    duration = getattr(info, "duration", None)
    if duration is None:
        return None

    try:
        return float(duration)
    except (TypeError, ValueError):
        return None


def _safe_message(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    if len(message) <= 180:
        return message
    return f"{message[:177].rstrip()}..."
