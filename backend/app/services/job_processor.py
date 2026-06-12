"""
job_processor.py

In-process background worker for long YouTube video jobs.

This module is intentionally free of FastAPI imports so it can be
unit-tested without starting the server. It reads settings at call
time (not at import time) so monkeypatching in tests works correctly.

Call ``process_youtube_job(job_id)`` from a FastAPI BackgroundTasks
callback. The function is safe to call from a background thread: it
never re-raises exceptions — all failures are written to the job store.
"""
from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


def process_youtube_job(job_id: str) -> None:
    """
    Execute the full pipeline for a queued long-video job.

    Stages in order:
      1. caption_fetch   — try YouTube captions
      2. audio_download  — only if captions are missing and STT is allowed
      3. transcribing    — local faster-whisper
      4. summarizing     — clean / chunk / summarise / save
      5. completed / failed

    This function never raises. All failures are stored in the job record.
    """
    # Import here so monkeypatching in tests is effective.
    from app.config import get_settings
    from app.services.youtube_caption_fetcher import (
        TranscriptNotFoundError,
        fetch_youtube_transcript,
    )
    from app.services.youtube_audio_downloader import (
        AudioDownloadError,
        delete_audio_file,
        download_youtube_audio,
    )
    from app.services.local_stt import LocalSTTError, transcribe_audio
    import app.storage.job_store as job_store

    # ------------------------------------------------------------------
    # Load job from store
    # ------------------------------------------------------------------
    job = job_store.get_job(job_id)
    if job is None:
        LOGGER.error("process_youtube_job: job_id %s not found in store", job_id)
        return

    source_url: str = job["source_url"]
    language: str = job["language"]
    title: str | None = job["title"]
    use_stt_fallback: bool = bool(job.get("use_stt_fallback", False))

    # ------------------------------------------------------------------
    # Stage: caption_fetch
    # ------------------------------------------------------------------
    try:
        job_store.update_job(
            job_id,
            status="running",
            stage="caption_fetch",
            progress_percent=5,
            message="กำลังดึง subtitle/caption จาก YouTube",
        )
    except Exception as exc:
        LOGGER.error("process_youtube_job: failed to update job %s to running: %s", job_id, exc)
        return

    # Try captions first.
    fetched: dict[str, Any] | None = None
    try:
        fetched = fetch_youtube_transcript(source_url, language)
    except TranscriptNotFoundError:
        fetched = None
    except Exception as exc:
        _fail(job_store, job_id, f"Caption fetch error: {type(exc).__name__}: {_safe_str(exc)}")
        return

    # ------------------------------------------------------------------
    # Caption succeeded — jump straight to summarising
    # ------------------------------------------------------------------
    if fetched is not None:
        youtube_video_id = str(fetched["video_id"])
        transcript_text = str(fetched["transcript"])
        extra_fields: dict[str, Any] = {
            "transcript_source": "youtube_caption",
            "youtube_video_id": youtube_video_id,
            "transcript_language": str(fetched.get("transcript_language", language)),
            "transcript_is_generated": bool(fetched.get("is_generated", False)),
        }
        _run_pipeline(
            job_store=job_store,
            job_id=job_id,
            title=title or f"YouTube Video {youtube_video_id}",
            source_url=source_url,
            language=language,
            transcript=transcript_text,
            extra_video_fields=extra_fields,
        )
        return

    # ------------------------------------------------------------------
    # Caption not found — check STT fallback eligibility
    # ------------------------------------------------------------------
    if not use_stt_fallback:
        _fail(
            job_store,
            job_id,
            "ไม่พบ subtitle/caption สำหรับวิดีโอนี้ และไม่ได้เปิดใช้งาน STT fallback",
            reason="transcript_not_found",
        )
        return

    settings = get_settings()
    if not settings.is_local_stt_enabled:
        _fail(
            job_store,
            job_id,
            "ไม่พบ subtitle/caption และ local STT ยังไม่ได้เปิดใช้งาน",
            reason="local_stt_disabled",
        )
        return

    # ------------------------------------------------------------------
    # Stage: audio_download
    # ------------------------------------------------------------------
    try:
        job_store.update_job(
            job_id,
            stage="audio_download",
            progress_percent=20,
            message="กำลังดาวน์โหลดเสียงจาก YouTube",
        )
    except Exception as exc:
        LOGGER.error("process_youtube_job: failed to update stage audio_download for %s: %s", job_id, exc)

    audio_path: str | None = None
    try:
        try:
            audio = download_youtube_audio(
                source_url,
                settings.stt_audio_dir,
                settings.stt_max_duration_seconds,
            )
            audio_path = str(audio["audio_path"])
            youtube_video_id = str(audio["youtube_video_id"])
        except AudioDownloadError as exc:
            _fail(job_store, job_id, f"ดาวน์โหลดเสียงไม่สำเร็จ: {_safe_str(exc)}")
            return

        # ---------------------------------------------------------------
        # Stage: transcribing
        # ---------------------------------------------------------------
        try:
            job_store.update_job(
                job_id,
                stage="transcribing",
                progress_percent=40,
                message="กำลัง transcribe เสียง (อาจใช้เวลานาน)",
            )
        except Exception as exc:
            LOGGER.error("process_youtube_job: failed to update stage transcribing for %s: %s", job_id, exc)

        try:
            stt_result = transcribe_audio(audio_path, language)
        except LocalSTTError as exc:
            _fail(job_store, job_id, f"Transcription ไม่สำเร็จ: {_safe_str(exc)}")
            return

    finally:
        # Always clean up the temporary audio file.
        if audio_path:
            delete_audio_file(audio_path)

    # ------------------------------------------------------------------
    # Pipeline: clean / chunk / summarise / save
    # ------------------------------------------------------------------
    extra_stt_fields: dict[str, Any] = {
        "transcript_source": "local_stt",
        "youtube_video_id": youtube_video_id,
        "transcript_language": str(stt_result.get("detected_language") or language),
        "transcript_is_generated": True,
        "stt_provider": str(stt_result["stt_provider"]),
        "stt_model_size": str(stt_result["stt_model_size"]),
        "audio_source": str(audio["audio_source"]),
        "audio_duration_seconds": audio.get("duration_seconds"),
        "stt_duration_seconds": stt_result.get("duration_seconds"),
    }
    _run_pipeline(
        job_store=job_store,
        job_id=job_id,
        title=title or f"YouTube Video {youtube_video_id}",
        source_url=source_url,
        language=language,
        transcript=str(stt_result["transcript"]),
        extra_video_fields=extra_stt_fields,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_pipeline(
    *,
    job_store: Any,
    job_id: str,
    title: str,
    source_url: str,
    language: str,
    transcript: str,
    extra_video_fields: dict[str, Any],
) -> None:
    """Clean, chunk, summarise, save video — then mark job completed."""
    from app.services.transcript_cleaner import clean_transcript
    from app.services.transcript_chunker import chunk_transcript
    from app.services.summary_provider import generate_summary_with_metadata
    from app.storage.video_store import save_video
    from datetime import datetime, timezone
    from uuid import uuid4

    try:
        job_store.update_job(
            job_id,
            stage="summarizing",
            progress_percent=75,
            message="กำลังสรุปเนื้อหา",
        )
    except Exception as exc:
        LOGGER.error("process_youtube_job: failed to update stage summarizing for %s: %s", job_id, exc)

    try:
        cleaned_transcript = clean_transcript(transcript)
        chunks = chunk_transcript(cleaned_transcript)
        summary_result = generate_summary_with_metadata(cleaned_transcript, chunks, language)
        video_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Quality analysis
        from app.services.transcript_quality import analyze_transcript_quality
        _transcript_source = extra_video_fields.get("transcript_source")
        quality_result = analyze_transcript_quality(
            cleaned_transcript,
            transcript_source=_transcript_source,
            language=language,
        )

        video: dict[str, Any] = {
            "video_id": video_id,
            "title": title,
            "source_url": source_url,
            "language": language,
            "cleaned_transcript": cleaned_transcript,
            "chunks": [chunk.model_dump() for chunk in chunks],
            "summary": summary_result.summary,
            "summary_provider": summary_result.summary_provider,
            "summary_fallback_used": summary_result.summary_fallback_used,
            "transcript_quality": quality_result["transcript_quality"],
            "transcript_warnings": quality_result["warnings"],
            "transcript_quality_signals": quality_result["quality_signals"],
            "created_at": created_at,
        }
        video.update(extra_video_fields)

        try:
            job_store.update_job(
                job_id,
                stage="saving",
                progress_percent=90,
                message="กำลังบันทึกผลลัพธ์",
            )
        except Exception as exc:
            LOGGER.error("process_youtube_job: failed to update stage saving for %s: %s", job_id, exc)

        save_video(video)
        job_store.complete_job(job_id, video_id=video_id, message="ประมวลผลวิดีโอเสร็จแล้ว")

    except Exception as exc:
        LOGGER.error(
            "process_youtube_job: pipeline failed for job %s: %s: %s",
            job_id,
            type(exc).__name__,
            exc,
        )
        _fail(job_store, job_id, f"ประมวลผลไม่สำเร็จ: {type(exc).__name__}: {_safe_str(exc)}")


def _fail(
    job_store: Any,
    job_id: str,
    error_message: str,
    reason: str | None = None,
) -> None:
    """Write a failed status to the job store without raising."""
    try:
        job_store.fail_job(job_id, error_message=error_message)
        LOGGER.warning(
            "process_youtube_job: job %s failed%s: %s",
            job_id,
            f" ({reason})" if reason else "",
            error_message,
        )
    except Exception as exc:
        LOGGER.error(
            "process_youtube_job: could not write failure for job %s: %s",
            job_id,
            exc,
        )


def _safe_str(exc: Exception, max_len: int = 200) -> str:
    """Return a safe, truncated string representation of an exception."""
    message = str(exc).replace("\n", " ").strip()
    if len(message) <= max_len:
        return message
    return f"{message[: max_len - 3].rstrip()}..."
