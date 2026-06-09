import logging
from typing import Any

from app.config import get_settings
from app.services.summarizer import SummaryGenerationResult, generate_rule_based_summary

LOGGER = logging.getLogger(__name__)


def generate_summary_with_metadata(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str = "thai",
) -> SummaryGenerationResult:
    settings = get_settings()
    if settings.summary_provider == "openai":
        if not settings.has_openai_config:
            _log_openai_config_missing(settings)
            return _rule_based_result(cleaned_transcript, chunks, language, fallback_used=True)

        try:
            from app.services.llm_summarizer import generate_llm_summary

            return SummaryGenerationResult(
                summary=generate_llm_summary(cleaned_transcript, chunks, language),
                summary_provider="openai",
                summary_fallback_used=False,
            )
        except Exception as exc:
            _log_openai_fallback(settings, reason="openai_call_failed", exc=exc)
            return _rule_based_result(cleaned_transcript, chunks, language, fallback_used=True)

    if settings.summary_provider == "ollama":
        if not settings.is_ollama_config_valid:
            _log_ollama_config_missing(settings)
            return _rule_based_result(cleaned_transcript, chunks, language, fallback_used=True)

        try:
            from app.services.ollama_summarizer import generate_ollama_summary

            return SummaryGenerationResult(
                summary=generate_ollama_summary(cleaned_transcript, chunks, language),
                summary_provider="ollama",
                summary_fallback_used=False,
            )
        except Exception as exc:
            _log_ollama_fallback(settings, reason="ollama_call_failed", exc=exc)
            return _rule_based_result(cleaned_transcript, chunks, language, fallback_used=True)

    return _rule_based_result(cleaned_transcript, chunks, language, fallback_used=False)


def _rule_based_result(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str,
    fallback_used: bool,
) -> SummaryGenerationResult:
    return SummaryGenerationResult(
        summary=generate_rule_based_summary(cleaned_transcript, chunks, language),
        summary_provider="rule_based",
        summary_fallback_used=fallback_used,
    )


def _log_openai_fallback(settings, reason: str, exc: Exception | None = None) -> None:
    LOGGER.warning(
        "OpenAI summary fallback: requested_provider=%s model=%s api_key_present=%s "
        "config_valid=%s reason=%s exception_class=%s exception_message=%s",
        settings.summary_provider,
        settings.openai_model,
        settings.openai_api_key_present,
        settings.is_openai_config_valid,
        reason,
        exc.__class__.__name__ if exc else None,
        _safe_exception_message(exc, settings.openai_api_key) if exc else None,
    )


def _log_openai_config_missing(settings) -> None:
    LOGGER.warning(
        "OpenAI config missing: requested_provider=%s model=%s api_key_present=%s "
        "model_present=%s config_valid=%s",
        settings.summary_provider,
        settings.openai_model,
        settings.openai_api_key_present,
        settings.openai_model_present,
        settings.is_openai_config_valid,
    )


def _log_ollama_fallback(settings, reason: str, exc: Exception | None = None) -> None:
    LOGGER.warning(
        "Ollama summary fallback: requested_provider=%s base_url=%s model=%s "
        "config_valid=%s reason=%s exception_class=%s exception_message=%s",
        settings.summary_provider,
        settings.ollama_base_url,
        settings.ollama_model,
        settings.is_ollama_config_valid,
        reason,
        exc.__class__.__name__ if exc else None,
        _safe_exception_message(exc, None) if exc else None,
    )


def _log_ollama_config_missing(settings) -> None:
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


def _safe_exception_message(exc: Exception, secret: str | None) -> str:
    message = str(exc).replace("\n", " ").strip()
    if secret:
        message = message.replace(secret, "[redacted]")
    if len(message) <= 160:
        return message
    return f"{message[:157].rstrip()}..."
