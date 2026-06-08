from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import PlainTextResponse

from app.schemas import (
    AskVideoRequest,
    AskVideoResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
    VideoListItem,
)
from app.services.markdown_exporter import export_video_to_markdown
from app.services.qa_engine import answer_question
from app.services.summarizer import generate_summary
from app.services.transcript_chunker import chunk_transcript
from app.services.transcript_cleaner import clean_transcript
from app.storage.video_store import get_video, list_videos, save_video

app = FastAPI(
    title="izuna-video-lab",
    description="Manual transcript cleaning, chunking, rule-based summarization, keyword Q&A, and Markdown export API.",
    version="0.1.5",
)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "izuna-video-lab"}


@app.post("/api/videos/process", response_model=ProcessVideoResponse)
def process_video(payload: ProcessVideoRequest) -> ProcessVideoResponse:
    cleaned_transcript = clean_transcript(payload.transcript)
    chunks = chunk_transcript(cleaned_transcript)
    summary = generate_summary(cleaned_transcript, chunks, payload.language)
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
