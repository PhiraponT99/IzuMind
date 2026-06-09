from typing import Literal

from pydantic import BaseModel, Field, field_validator

Language = Literal["thai", "english"]
SummaryProvider = Literal["rule_based", "openai", "ollama"]


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


class ProcessYouTubeVideoRequest(BaseModel):
    source_url: str = Field(..., min_length=1)
    language: Language
    title: str | None = None
    use_stt_fallback: bool = False

    @field_validator("source_url")
    @classmethod
    def source_url_must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Source URL must not be empty.")
        return value.strip()

    @field_validator("title")
    @classmethod
    def normalize_optional_title(cls, value: str | None) -> str | None:
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
    summary_provider: SummaryProvider
    summary_fallback_used: bool


class ProcessYouTubeVideoResponse(ProcessVideoResponse):
    transcript_source: Literal["youtube_caption", "local_stt"]
    youtube_video_id: str
    transcript_language: str
    transcript_is_generated: bool
    stt_provider: str | None = None
    stt_model_size: str | None = None


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


class ConfigResponse(BaseModel):
    summary_provider: SummaryProvider
    openai_model: str | None
    openai_api_key_present: bool
    openai_model_present: bool
    openai_config_valid: bool
    ollama_base_url: str | None
    ollama_model: str | None
    ollama_base_url_present: bool
    ollama_model_present: bool
    ollama_config_valid: bool
    enable_local_stt: bool
    stt_provider: str
    stt_model_size: str
    stt_device: str
    stt_compute_type: str
    stt_audio_dir: str
    stt_max_duration_seconds: int
    env_file_exists: bool
    env_file_path: str


class OpenAISmokeTestResponse(BaseModel):
    ok: bool
    stage: Literal["config", "openai_call", "json_parse"]
    message: str
    openai_api_key_present: bool | None = None
    openai_model: str | None = None
    model: str | None = None
    output_preview: str | None = None


class OllamaSmokeTestResponse(BaseModel):
    ok: bool
    stage: Literal["config", "ollama_call", "json_parse"]
    message: str
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    model: str | None = None
    output_preview: str | None = None


class STTSmokeTestResponse(BaseModel):
    ok: bool
    stage: Literal["config"]
    enable_local_stt: bool
    stt_provider: str
    stt_model_size: str
    stt_device: str
    stt_compute_type: str
    message: str
    yt_dlp_import_ok: bool
    faster_whisper_import_ok: bool
