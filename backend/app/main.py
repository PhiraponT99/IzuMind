from datetime import datetime, timezone
import importlib.util
from uuid import uuid4

from fastapi import FastAPI
from fastapi import BackgroundTasks
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.schemas import (
    AskVideoRequest,
    AskVideoResponse,
    ConfigResponse,
    OllamaSmokeTestResponse,
    OpenAISmokeTestResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
    ProcessYouTubeVideoRequest,
    ProcessYouTubeVideoResponse,
    STTSmokeTestResponse,
    VideoListItem,
    ProcessYouTubeLongVideoRequest,
    JobStatusResponse,
    JobListResponse,
)
from app.services.llm_summarizer import run_openai_smoke_test
from app.services.local_stt import LocalSTTError, transcribe_audio
from app.services.markdown_exporter import export_video_to_markdown
from app.services.ollama_summarizer import run_ollama_smoke_test
from app.services.qa_engine import answer_question
from app.services.summary_provider import generate_summary_with_metadata
from app.services.transcript_chunker import chunk_transcript
from app.services.transcript_cleaner import clean_transcript
from app.services.youtube_caption_fetcher import TranscriptNotFoundError, fetch_youtube_transcript
from app.services.youtube_audio_downloader import AudioDownloadError, delete_audio_file, download_youtube_audio
from app.storage.video_store import get_video, list_videos, save_video
import app.storage.job_store as job_store
from app.services.job_processor import process_youtube_job

app = FastAPI(
    title="izuna-video-lab",
    description="Manual transcript cleaning, chunking, optional LLM summarization, keyword Q&A, and Markdown export API.",
    version="0.2.1",
)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "izuna-video-lab"}


@app.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        summary_provider=settings.summary_provider,
        openai_model=settings.openai_model,
        openai_api_key_present=settings.openai_api_key_present,
        openai_model_present=settings.openai_model_present,
        openai_config_valid=settings.is_openai_config_valid,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_base_url_present=settings.ollama_base_url_present,
        ollama_model_present=settings.ollama_model_present,
        ollama_config_valid=settings.is_ollama_config_valid,
        enable_local_stt=settings.enable_local_stt,
        stt_provider=settings.stt_provider,
        stt_model_size=settings.stt_model_size,
        stt_device=settings.stt_device,
        stt_compute_type=settings.stt_compute_type,
        stt_audio_dir=settings.stt_audio_dir,
        stt_max_duration_seconds=settings.stt_max_duration_seconds,
        env_file_exists=settings.env_file_exists,
        env_file_path=settings.env_file_path,
    )


@app.get("/api/llm/openai/smoke-test", response_model=OpenAISmokeTestResponse)
def openai_smoke_test() -> OpenAISmokeTestResponse:
    return OpenAISmokeTestResponse(**run_openai_smoke_test())


@app.get("/api/llm/ollama/smoke-test", response_model=OllamaSmokeTestResponse)
def ollama_smoke_test() -> OllamaSmokeTestResponse:
    return OllamaSmokeTestResponse(**run_ollama_smoke_test())


@app.get("/api/stt/smoke-test", response_model=STTSmokeTestResponse)
def stt_smoke_test() -> STTSmokeTestResponse:
    settings = get_settings()
    yt_dlp_import_ok = importlib.util.find_spec("yt_dlp") is not None
    faster_whisper_import_ok = importlib.util.find_spec("faster_whisper") is not None
    ok = (
        settings.is_local_stt_enabled
        and settings.stt_provider == "faster_whisper"
        and yt_dlp_import_ok
        and faster_whisper_import_ok
    )
    if not settings.is_local_stt_enabled:
        message = "Local STT is disabled."
    elif ok:
        message = "Local STT config is enabled and required imports are available."
    else:
        message = "Local STT is enabled but required imports are missing."

    return STTSmokeTestResponse(
        ok=ok,
        stage="config",
        enable_local_stt=settings.enable_local_stt,
        stt_provider=settings.stt_provider,
        stt_model_size=settings.stt_model_size,
        stt_device=settings.stt_device,
        stt_compute_type=settings.stt_compute_type,
        message=message,
        yt_dlp_import_ok=yt_dlp_import_ok,
        faster_whisper_import_ok=faster_whisper_import_ok,
    )


@app.post("/api/videos/process", response_model=ProcessVideoResponse)
def process_video(payload: ProcessVideoRequest) -> ProcessVideoResponse:
    return process_transcript(
        title=payload.title,
        source_url=payload.source_url,
        language=payload.language,
        transcript=payload.transcript,
    )


@app.post("/api/videos/process-youtube", response_model=ProcessYouTubeVideoResponse)
def process_youtube_video(payload: ProcessYouTubeVideoRequest):
    try:
        fetched = fetch_youtube_transcript(payload.source_url, payload.language)
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "reason": "invalid_youtube_url",
                "message": str(exc),
                "source_url": payload.source_url,
            },
        )
    except TranscriptNotFoundError as exc:
        if not payload.use_stt_fallback:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "reason": "transcript_not_found",
                    "message": str(exc),
                    "source_url": payload.source_url,
                },
            )

        settings = get_settings()
        if not settings.is_local_stt_enabled:
            return JSONResponse(
                status_code=422,
                content={
                    "ok": False,
                    "reason": "local_stt_disabled",
                    "message": "ไม่พบ subtitle/caption และ local STT ยังไม่ได้เปิดใช้งาน",
                    "source_url": payload.source_url,
                },
            )

        audio_path = None
        try:
            try:
                audio = download_youtube_audio(
                    payload.source_url,
                    settings.stt_audio_dir,
                    settings.stt_max_duration_seconds,
                )
                audio_path = str(audio["audio_path"])
                stt_result = transcribe_audio(audio_path, payload.language)
            finally:
                if audio_path:
                    delete_audio_file(audio_path)
        except AudioDownloadError as audio_exc:
            return JSONResponse(
                status_code=422,
                content={
                    "ok": False,
                    "reason": "audio_download_failed",
                    "message": str(audio_exc),
                    "source_url": payload.source_url,
                },
            )
        except LocalSTTError as stt_exc:
            return JSONResponse(
                status_code=422,
                content={
                    "ok": False,
                    "reason": "local_stt_failed",
                    "message": str(stt_exc),
                    "source_url": payload.source_url,
                },
            )

        youtube_video_id = str(audio["youtube_video_id"])
        base_response = process_transcript(
            title=payload.title or f"YouTube Video {youtube_video_id}",
            source_url=payload.source_url,
            language=payload.language,
            transcript=str(stt_result["transcript"]),
            extra_video_fields={
                "transcript_source": "local_stt",
                "youtube_video_id": youtube_video_id,
                "transcript_language": str(stt_result.get("detected_language") or payload.language),
                "transcript_is_generated": True,
                "stt_provider": str(stt_result["stt_provider"]),
                "stt_model_size": str(stt_result["stt_model_size"]),
                "audio_source": str(audio["audio_source"]),
                "audio_duration_seconds": audio.get("duration_seconds"),
                "stt_duration_seconds": stt_result.get("duration_seconds"),
            },
        )

        return ProcessYouTubeVideoResponse(
            **base_response.model_dump(),
            transcript_source="local_stt",
            youtube_video_id=youtube_video_id,
            transcript_language=str(stt_result.get("detected_language") or payload.language),
            transcript_is_generated=True,
            stt_provider=str(stt_result["stt_provider"]),
            stt_model_size=str(stt_result["stt_model_size"]),
        )

    youtube_video_id = str(fetched["video_id"])
    base_response = process_transcript(
        title=payload.title or f"YouTube Video {youtube_video_id}",
        source_url=payload.source_url,
        language=payload.language,
        transcript=str(fetched["transcript"]),
        extra_video_fields={
            "transcript_source": "youtube_caption",
            "youtube_video_id": youtube_video_id,
            "transcript_language": str(fetched["transcript_language"]),
            "transcript_is_generated": bool(fetched["is_generated"]),
        },
    )

    return ProcessYouTubeVideoResponse(
        **base_response.model_dump(),
        transcript_source="youtube_caption",
        youtube_video_id=youtube_video_id,
        transcript_language=str(fetched["transcript_language"]),
        transcript_is_generated=bool(fetched["is_generated"]),
    )


def process_transcript(
    title: str,
    source_url: str | None,
    language: str,
    transcript: str,
    extra_video_fields: dict | None = None,
) -> ProcessVideoResponse:
    cleaned_transcript = clean_transcript(transcript)
    chunks = chunk_transcript(cleaned_transcript)
    summary_result = generate_summary_with_metadata(cleaned_transcript, chunks, language)
    summary = summary_result.summary
    video_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    video = {
        "video_id": video_id,
        "title": title,
        "source_url": source_url,
        "language": language,
        "cleaned_transcript": cleaned_transcript,
        "chunks": [chunk.model_dump() for chunk in chunks],
        "summary": summary,
        "summary_provider": summary_result.summary_provider,
        "summary_fallback_used": summary_result.summary_fallback_used,
        "created_at": created_at,
    }
    if extra_video_fields:
        video.update(extra_video_fields)
    save_video(video)

    return ProcessVideoResponse(
        video_id=video_id,
        title=title,
        source_url=source_url,
        language=language,
        cleaned_transcript=cleaned_transcript,
        chunks=chunks,
        summary=summary,
        summary_provider=summary_result.summary_provider,
        summary_fallback_used=summary_result.summary_fallback_used,
    )


@app.get("/api/videos", response_model=list[VideoListItem])
def list_saved_videos() -> list[VideoListItem]:
    return [
        VideoListItem(
            video_id=str(video.get("video_id", "")),
            title=str(video.get("title", "")),
            source_url=video.get("source_url"),
            language=video.get("language", "english"),
            created_at=str(video.get("created_at", "")),
        )
        for video in list_videos()
    ]


@app.post("/api/videos/{video_id}/ask", response_model=AskVideoResponse)
def ask_video(video_id: str, payload: AskVideoRequest) -> AskVideoResponse:
    video = get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    qa_result = answer_question(payload.question, video.get("chunks", []))

    return AskVideoResponse(
        video_id=video_id,
        question=payload.question,
        answer=qa_result["answer"],
        related_chunks=qa_result["related_chunks"],
    )


@app.get("/api/videos/{video_id}/export/markdown", response_class=PlainTextResponse)
def export_video_markdown(video_id: str) -> PlainTextResponse:
    video = get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found.")

    markdown = export_video_to_markdown(video)
    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
    )


@app.post("/api/videos/process-youtube-long", response_model=JobStatusResponse, status_code=202)
def process_youtube_long(
    payload: ProcessYouTubeLongVideoRequest,
    background_tasks: BackgroundTasks,
):
    job = job_store.create_job(
        source_url=payload.source_url,
        title=payload.title,
        language=payload.language,
        use_stt_fallback=payload.use_stt_fallback,
    )
    background_tasks.add_task(process_youtube_job, job["job_id"])
    return JobStatusResponse(**job)


@app.get("/api/jobs/{job_id}")
def get_job_endpoint(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "reason": "job_not_found",
                "message": "ไม่พบ job_id นี้",
            },
        )
    return JobStatusResponse(**job)


@app.get("/api/jobs", response_model=list[JobStatusResponse])
def list_jobs_endpoint(limit: int = 50):
    clamped_limit = max(1, min(limit, 100))
    jobs = job_store.list_jobs(limit=clamped_limit)
    return [JobStatusResponse(**job) for job in jobs]

