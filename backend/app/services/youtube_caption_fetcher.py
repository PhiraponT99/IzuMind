from typing import Any

from app.services.youtube_utils import extract_youtube_video_id


class TranscriptNotFoundError(Exception):
    """Raised when a YouTube transcript cannot be fetched safely."""


def fetch_youtube_transcript(source_url: str, language: str = "thai") -> dict:
    video_id = extract_youtube_video_id(source_url)
    languages = _language_priority(language)

    try:
        transcript = _select_transcript(video_id, languages)
        segments = transcript.fetch()
    except Exception as exc:
        raise TranscriptNotFoundError(
            "ไม่พบ subtitle/caption สำหรับวิดีโอนี้ กรุณาวาง transcript เองผ่าน /api/videos/process"
        ) from exc

    transcript_text = " ".join(_segment_text(segment) for segment in segments)
    transcript_text = " ".join(transcript_text.split())
    if not transcript_text:
        raise TranscriptNotFoundError(
            "ไม่พบ subtitle/caption สำหรับวิดีโอนี้ กรุณาวาง transcript เองผ่าน /api/videos/process"
        )

    return {
        "video_id": video_id,
        "transcript": transcript_text,
        "transcript_language": getattr(transcript, "language_code", languages[0]),
        "transcript_source": "youtube_caption",
        "is_generated": bool(getattr(transcript, "is_generated", False)),
    }


def _select_transcript(video_id: str, languages: list[str]) -> Any:
    from youtube_transcript_api import YouTubeTranscriptApi

    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    try:
        return transcript_list.find_manually_created_transcript(languages)
    except Exception:
        return transcript_list.find_generated_transcript(languages)


def _language_priority(language: str) -> list[str]:
    normalized = language.lower().strip()
    if normalized == "thai":
        return ["th", "en"]
    if normalized == "english":
        return ["en", "th"]
    return ["th", "en"]


def _segment_text(segment: Any) -> str:
    if isinstance(segment, dict):
        return str(segment.get("text", ""))

    return str(getattr(segment, "text", ""))
