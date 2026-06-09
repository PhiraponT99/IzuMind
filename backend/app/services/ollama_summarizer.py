import json
import logging
from typing import Any

import httpx

from app.config import Settings, get_settings

LOGGER = logging.getLogger(__name__)
MODEL_OUTPUT_PREVIEW_CHARS = 300
OLLAMA_TIMEOUT_SECONDS = 60

SUMMARY_KEYS = {
    "tldr",
    "main_ideas",
    "key_takeaways",
    "action_items",
    "questions_to_think",
}


def generate_ollama_summary(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str = "thai",
) -> dict:
    settings = get_settings()
    if not settings.should_use_ollama_summary:
        raise RuntimeError("Ollama summary provider is not configured.")

    output_text = _call_ollama_for_text(
        prompt=_build_prompt(cleaned_transcript, chunks, language),
        settings=settings,
    )
    summary = _parse_json_output(output_text, settings)
    _validate_summary_shape(summary)
    return summary


def run_ollama_smoke_test() -> dict:
    settings = get_settings()
    if not settings.is_ollama_config_valid:
        LOGGER.warning(
            "Ollama config missing: requested_provider=%s base_url=%s model=%s "
            "base_url_present=%s model_present=%s config_valid=%s",
            settings.summary_provider,
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_base_url_present,
            settings.ollama_model_present,
            settings.is_ollama_config_valid,
        )
        return {
            "ok": False,
            "stage": "config",
            "message": "Ollama config is invalid",
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
        }

    try:
        output_text = _call_ollama_for_text(
            prompt='Return only this JSON: {"ok": true, "message": "pong"}',
            settings=settings,
        )
    except Exception as exc:
        LOGGER.warning(
            "Ollama smoke test call failed: provider=%s base_url=%s model=%s "
            "config_valid=%s exception_class=%s exception_message=%s",
            settings.summary_provider,
            settings.ollama_base_url,
            settings.ollama_model,
            settings.is_ollama_config_valid,
            exc.__class__.__name__,
            _safe_message(str(exc)),
        )
        return {
            "ok": False,
            "stage": "ollama_call",
            "model": settings.ollama_model,
            "message": f"Ollama call failed: {exc.__class__.__name__}",
            "output_preview": None,
        }

    try:
        parsed = _parse_json_output(output_text, settings)
    except json.JSONDecodeError as exc:
        LOGGER.warning(
            "Ollama smoke test JSON parse failed: exception_class=%s exception_message=%s "
            "model_output_preview=%s",
            exc.__class__.__name__,
            _safe_message(str(exc)),
            _safe_model_output_preview(output_text),
        )
        return {
            "ok": False,
            "stage": "json_parse",
            "model": settings.ollama_model,
            "message": "Ollama smoke-test JSON parse failed",
            "output_preview": _safe_model_output_preview(output_text),
        }

    return {
        "ok": parsed.get("ok") is True,
        "stage": "ollama_call",
        "model": settings.ollama_model,
        "message": str(parsed.get("message", "Ollama smoke test completed")),
        "output_preview": _safe_model_output_preview(output_text),
    }


def _call_ollama_for_text(prompt: str, settings: Settings) -> str:
    if settings.ollama_base_url is None or settings.ollama_model is None:
        raise RuntimeError("Ollama config is incomplete.")

    LOGGER.info(
        "Ollama request starting: provider=%s base_url=%s model=%s config_valid=%s",
        settings.summary_provider,
        settings.ollama_base_url,
        settings.ollama_model,
        settings.is_ollama_config_valid,
    )
    response = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You summarize transcripts into strict JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("message", {}).get("content", ""))


def _build_prompt(cleaned_transcript: str, chunks: list[Any], language: str) -> str:
    output_language = "Thai only" if language == "thai" else "English only"
    return (
        "Return JSON only. Do not wrap the JSON in Markdown.\n"
        f"Output language: {output_language}.\n"
        "Ground the summary only in the transcript. Do not invent details.\n"
        "Keep bullets concise and useful.\n"
        "Use exactly this JSON shape:\n"
        "{\n"
        '  "tldr": "string",\n'
        '  "main_ideas": ["string"],\n'
        '  "key_takeaways": ["string"],\n'
        '  "action_items": ["string"],\n'
        '  "questions_to_think": ["string"]\n'
        "}\n\n"
        "Cleaned transcript:\n"
        f"{cleaned_transcript}\n\n"
        "Transcript chunks:\n"
        f"{_format_chunks(chunks)}"
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


def _parse_json_output(output_text: str, settings: Settings) -> dict:
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        LOGGER.warning(
            "Ollama summary JSON parse failed: provider=%s base_url=%s model=%s "
            "exception_class=%s exception_message=%s model_output_preview=%s",
            settings.summary_provider,
            settings.ollama_base_url,
            settings.ollama_model,
            exc.__class__.__name__,
            _safe_message(str(exc)),
            _safe_model_output_preview(output_text),
        )
        raise


def _validate_summary_shape(summary: dict) -> None:
    if set(summary) != SUMMARY_KEYS:
        raise ValueError("Ollama summary returned an unexpected JSON shape.")

    if not isinstance(summary["tldr"], str):
        raise ValueError("Ollama summary tldr must be a string.")

    for key in SUMMARY_KEYS - {"tldr"}:
        if not isinstance(summary[key], list):
            raise ValueError(f"Ollama summary {key} must be a list.")
        if not all(isinstance(item, str) for item in summary[key]):
            raise ValueError(f"Ollama summary {key} must contain only strings.")


def _safe_model_output_preview(output_text: str) -> str:
    return _safe_message(output_text[:MODEL_OUTPUT_PREVIEW_CHARS])


def _safe_message(message: str) -> str:
    return str(message).replace("\n", " ").strip()
