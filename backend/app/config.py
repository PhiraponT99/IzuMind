import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

VALID_SUMMARY_PROVIDERS = {"rule_based", "openai", "ollama"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class Settings:
    summary_provider: str
    openai_api_key: str | None
    openai_model: str | None
    ollama_base_url: str | None
    ollama_model: str | None
    env_file_path: str
    env_file_exists: bool

    @property
    def is_openai_requested(self) -> bool:
        return self.summary_provider == "openai"

    @property
    def is_ollama_requested(self) -> bool:
        return self.summary_provider == "ollama"

    @property
    def is_openai_config_valid(self) -> bool:
        return self.openai_api_key_present and self.openai_model_present

    @property
    def is_ollama_config_valid(self) -> bool:
        return self.ollama_base_url_present and self.ollama_model_present

    @property
    def openai_api_key_present(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def openai_model_present(self) -> bool:
        return bool(self.openai_model)

    @property
    def ollama_base_url_present(self) -> bool:
        return bool(self.ollama_base_url)

    @property
    def ollama_model_present(self) -> bool:
        return bool(self.ollama_model)

    @property
    def has_openai_config(self) -> bool:
        return self.is_openai_config_valid

    @property
    def should_use_openai_summary(self) -> bool:
        return self.is_openai_requested and self.is_openai_config_valid

    @property
    def should_use_ollama_summary(self) -> bool:
        return self.is_ollama_requested and self.is_ollama_config_valid


def get_settings() -> Settings:
    env_file_values = _read_env_file(ENV_FILE)
    summary_provider = _get_config_value("SUMMARY_PROVIDER", env_file_values, "rule_based")
    summary_provider = (summary_provider or "rule_based").lower().strip()
    if summary_provider not in VALID_SUMMARY_PROVIDERS:
        summary_provider = "rule_based"

    return Settings(
        summary_provider=summary_provider,
        openai_api_key=_empty_to_none(_get_config_value("OPENAI_API_KEY", env_file_values)),
        openai_model=_empty_to_none(_get_config_value("OPENAI_MODEL", env_file_values)),
        ollama_base_url=_normalize_base_url(
            _get_config_value("OLLAMA_BASE_URL", env_file_values, "http://localhost:11434")
        ),
        ollama_model=_empty_to_none(_get_config_value("OLLAMA_MODEL", env_file_values)),
        env_file_path=str(ENV_FILE),
        env_file_exists=ENV_FILE.exists(),
    )


def _get_config_value(
    key: str,
    env_file_values: dict[str, str],
    default: str | None = None,
) -> str | None:
    value = os.getenv(key)
    if value is not None:
        return value

    return env_file_values.get(key, default)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    try:
        values = dotenv_values(path)
    except OSError:
        return {}

    return {
        key: value
        for key, value in values.items()
        if key and isinstance(value, str)
    }


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _normalize_base_url(value: str | None) -> str | None:
    normalized = _empty_to_none(value)
    if normalized is None:
        return None

    return normalized.rstrip("/")
