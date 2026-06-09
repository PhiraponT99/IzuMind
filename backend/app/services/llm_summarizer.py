import json
import logging
from typing import Any

from app.config import Settings, get_settings

LOGGER = logging.getLogger(__name__)
MODEL_OUTPUT_PREVIEW_CHARS = 300

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


def run_openai_smoke_test() -> dict:
    settings = get_settings()
    if not settings.is_openai_config_valid:
        LOGGER.warning(
            "OpenAI config missing: requested_provider=%s model=%s api_key_present=%s "
            "model_present=%s config_valid=%s",
            settings.summary_provider,
            settings.openai_model,
            settings.openai_api_key_present,
            settings.openai_model_present,
            settings.is_openai_config_valid,
        )
        return {
            "ok": False,
            "stage": "config",
            "message": "OpenAI config is invalid",
            "openai_api_key_present": settings.openai_api_key_present,
            "openai_model": settings.openai_model,
        }

    try:
        output_text = _call_openai_for_text(
            prompt='Return only this JSON: {"ok": true, "message": "pong"}',
            settings=settings,
        )
    except Exception as exc:
        LOGGER.warning(
            "OpenAI smoke test call failed: provider=%s model=%s api_key_present=%s "
            "config_valid=%s exception_class=%s exception_message=%s",
            settings.summary_provider,
            settings.openai_model,
            settings.openai_api_key_present,
            settings.is_openai_config_valid,
            exc.__class__.__name__,
            _safe_message(str(exc), settings.openai_api_key),
        )
        return {
            "ok": False,
            "stage": "openai_call",
            "model": settings.openai_model,
            "message": f"OpenAI call failed: {exc.__class__.__name__}",
            "output_preview": None,
        }

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        LOGGER.warning(
            "OpenAI smoke test JSON parse failed: exception_class=%s exception_message=%s "
            "model_output_preview=%s",
            exc.__class__.__name__,
            _safe_message(str(exc), settings.openai_api_key),
            _safe_model_output_preview(output_text, settings.openai_api_key),
        )
        return {
            "ok": False,
            "stage": "json_parse",
            "model": settings.openai_model,
            "message": "OpenAI smoke-test JSON parse failed",
            "output_preview": _safe_model_output_preview(output_text, settings.openai_api_key),
        }

    return {
        "ok": parsed.get("ok") is True,
        "stage": "openai_call",
        "model": settings.openai_model,
        "message": str(parsed.get("message", "OpenAI smoke test completed")),
        "output_preview": _safe_model_output_preview(output_text, settings.openai_api_key),
    }


def _generate_openai_summary(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str,
    settings: Settings,
) -> dict:
    output_text = _call_openai_for_text(
        prompt=_build_prompt(cleaned_transcript, chunks, language),
        settings=settings,
        text_format={
            "type": "json_schema",
            "name": "video_summary",
            "strict": True,
            "schema": SUMMARY_SCHEMA,
        },
    )
    try:
        summary = json.loads(output_text)
    except json.JSONDecodeError as exc:
        LOGGER.warning(
            "OpenAI summary JSON parse failed: exception_class=%s exception_message=%s "
            "model_output_preview=%s",
            exc.__class__.__name__,
            _safe_message(str(exc), settings.openai_api_key),
            _safe_model_output_preview(output_text, settings.openai_api_key),
        )
        raise

    _validate_summary_shape(summary)
    return summary


def _call_openai_for_text(
    prompt: str,
    settings: Settings,
    text_format: dict | None = None,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    kwargs = {
        "model": settings.openai_model,
        "input": prompt,
    }
    if text_format is not None:
        kwargs["text"] = {"format": text_format}

    LOGGER.info(
        "OpenAI request starting: provider=%s model=%s api_key_present=%s config_valid=%s",
        settings.summary_provider,
        settings.openai_model,
        settings.openai_api_key_present,
        settings.is_openai_config_valid,
    )
    response = client.responses.create(**kwargs)
    return str(getattr(response, "output_text", ""))


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


def _safe_model_output_preview(output_text: str, api_key: str | None) -> str:
    preview = output_text[:MODEL_OUTPUT_PREVIEW_CHARS]
    return _safe_message(preview, api_key)


def _safe_message(message: str, api_key: str | None) -> str:
    safe = str(message).replace("\n", " ").strip()
    if api_key:
        safe = safe.replace(api_key, "[redacted]")
    return safe
