import json
from typing import Any

from app.config import Settings, get_settings

SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tldr": {"type": "string"},
        "main_ideas": {"type": "array", "items": {"type": "string"}},
        "key_takeaways": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": {"type": "string"}},
        "questions_to_think": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "tldr",
        "main_ideas",
        "key_takeaways",
        "action_items",
        "questions_to_think",
    ],
}


def generate_llm_summary(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str = "thai",
) -> dict:
    settings = get_settings()
    if not settings.should_use_openai_summary:
        raise RuntimeError("OpenAI summary provider is not configured.")

    return _generate_openai_summary(cleaned_transcript, chunks, language, settings)


def _generate_openai_summary(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str,
    settings: Settings,
) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_model,
        input=_build_prompt(cleaned_transcript, chunks, language),
        text={
            "format": {
                "type": "json_schema",
                "name": "video_summary",
                "strict": True,
                "schema": SUMMARY_SCHEMA,
            }
        },
    )

    output_text = getattr(response, "output_text", "")
    summary = json.loads(output_text)
    _validate_summary_shape(summary)
    return summary


def _build_prompt(cleaned_transcript: str, chunks: list[Any], language: str) -> str:
    output_language = "Thai only" if language == "thai" else "English only"
    chunk_preview = _format_chunks(chunks)
    return (
        "You summarize video transcripts into structured study notes.\n"
        f"Output language: {output_language}.\n"
        "Ground the summary only in the transcript. Do not invent details.\n"
        "Keep every bullet concise and useful.\n"
        "Return valid JSON only with exactly these keys: "
        "tldr, main_ideas, key_takeaways, action_items, questions_to_think.\n\n"
        "Cleaned transcript:\n"
        f"{cleaned_transcript}\n\n"
        "Transcript chunks:\n"
        f"{chunk_preview}"
    )


def _format_chunks(chunks: list[Any]) -> str:
    formatted_chunks = []
    for chunk in chunks[:8]:
        if isinstance(chunk, dict):
            chunk_index = chunk.get("chunk_index", "?")
            text = chunk.get("text", "")
        else:
            chunk_index = getattr(chunk, "chunk_index", "?")
            text = getattr(chunk, "text", "")

        formatted_chunks.append(f"Chunk {chunk_index}: {text}")

    return "\n".join(formatted_chunks)


def _validate_summary_shape(summary: dict) -> None:
    expected_keys = set(SUMMARY_SCHEMA["required"])
    if set(summary) != expected_keys:
        raise ValueError("LLM summary returned an unexpected JSON shape.")

    if not isinstance(summary["tldr"], str):
        raise ValueError("LLM summary tldr must be a string.")

    for key in expected_keys - {"tldr"}:
        if not isinstance(summary[key], list):
            raise ValueError(f"LLM summary {key} must be a list.")
        if not all(isinstance(item, str) for item in summary[key]):
            raise ValueError(f"LLM summary {key} must contain only strings.")
