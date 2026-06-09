from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi import HTTPException
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
    VideoListItem,
)
from app.services.llm_summarizer import run_openai_smoke_test
from app.services.markdown_exporter import export_video_to_markdown
from app.services.ollama_summarizer import run_ollama_smoke_test
from app.services.qa_engine import answer_question
from app.services.summary_provider import generate_summary_with_metadata
from app.services.transcript_chunker import chunk_transcript
from app.services.transcript_cleaner import clean_transcript
from app.storage.video_store import get_video, list_videos, save_video

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
        env_file_exists=settings.env_file_exists,
        env_file_path=settings.env_file_path,
    )


@app.get("/api/llm/openai/smoke-test", response_model=OpenAISmokeTestResponse)
def openai_smoke_test() -> OpenAISmokeTestResponse:
    return OpenAISmokeTestResponse(**run_openai_smoke_test())


@app.get("/api/llm/ollama/smoke-test", response_model=OllamaSmokeTestResponse)
def ollama_smoke_test() -> OllamaSmokeTestResponse:
    return OllamaSmokeTestResponse(**run_ollama_smoke_test())


@app.post("/api/videos/process", response_model=ProcessVideoResponse)
def process_video(payload: ProcessVideoRequest) -> ProcessVideoResponse:
    cleaned_transcript = clean_transcript(payload.transcript)
    chunks = chunk_transcript(cleaned_transcript)
    summary_result = generate_summary_with_metadata(cleaned_transcript, chunks, payload.language)
    summary = summary_result.summary
    video_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    video = {
        "video_id": video_id,
        "title": payload.title,
        "source_url": payload.source_url,
        "language": payload.language,
        "cleaned_transcript": cleaned_transcript,
        "chunks": [chunk.model_dump() for chunk in chunks],
        "summary": summary,
        "summary_provider": summary_result.summary_provider,
        "summary_fallback_used": summary_result.summary_fallback_used,
        "created_at": created_at,
    }
    save_video(video)

    return ProcessVideoResponse(
        video_id=video_id,
        title=payload.title,
        source_url=payload.source_url,
        language=payload.language,
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
