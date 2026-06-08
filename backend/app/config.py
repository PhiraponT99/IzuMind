import os
from dataclasses import dataclass
from pathlib import Path

VALID_SUMMARY_PROVIDERS = {"rule_based", "openai"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str | None
    summary_provider: str

    @property
    def has_openai_config(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)

    @property
    def should_use_openai_summary(self) -> bool:
        return self.summary_provider == "openai" and self.has_openai_config


def get_settings() -> Settings:
    env_file_values = _read_env_file(ENV_FILE)
    summary_provider = _get_config_value("SUMMARY_PROVIDER", env_file_values, "rule_based")
    summary_provider = summary_provider.lower().strip()
    if summary_provider not in VALID_SUMMARY_PROVIDERS:
        summary_provider = "rule_based"

    return Settings(
        openai_api_key=_empty_to_none(_get_config_value("OPENAI_API_KEY", env_file_values)),
        openai_model=_empty_to_none(_get_config_value("OPENAI_MODEL", env_file_values)),
        summary_provider=summary_provider,
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

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value

    return values


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None
