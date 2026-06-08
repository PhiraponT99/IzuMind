from typing import Literal

from pydantic import BaseModel, Field, field_validator

Language = Literal["thai", "english"]


class ProcessVideoRequest(BaseModel):
    title: str = Field(..., min_length=1)
    source_url: str | None = None
    language: Language
    transcript: str = Field(..., min_length=1)

    @field_validator("title", "transcript")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field must not be empty.")
        return value.strip()

    @field_validator("source_url")
    @classmethod
    def normalize_optional_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None


class TranscriptChunk(BaseModel):
    chunk_index: int
    text: str
    char_count: int


class RelatedChunk(TranscriptChunk):
    score: int


class Summary(BaseModel):
    tldr: str
    main_ideas: list[str]
    key_takeaways: list[str]
    action_items: list[str]
    questions_to_think: list[str]


class ProcessVideoResponse(BaseModel):
    video_id: str
    title: str
    source_url: str | None
    language: Language
    cleaned_transcript: str
    chunks: list[TranscriptChunk]
    summary: Summary


class AskVideoRequest(BaseModel):
    question: str = Field(..., min_length=1)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Question must not be empty.")
        return value.strip()


class AskVideoResponse(BaseModel):
    video_id: str
    question: str
    answer: str
    related_chunks: list[RelatedChunk]


class VideoListItem(BaseModel):
    video_id: str
    title: str
    source_url: str | None
    language: Language
    created_at: str
