from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


# -.-.-.-
def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"


# -.-.-.-
def _platform_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(
        platform.system(), "linux"
    )


class AntonellaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ANTONELLA_",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    os_system: Literal["windows", "mac", "linux"] = Field(default_factory=_platform_os)
    assistant_name: str = "Antonella"
    user_name: str = ""
    voice_name: str = "Kore"
    voice_style: str = "feminine, warm, natural, calm, confident, concise and conversational"
    morning_brief_enabled: bool = True
    plugins_enabled: dict[str, bool] = Field(default_factory=dict)
    ui_color: str = ""
    llm_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"
    llm_provider: str = "ollama"

    model_provider_preference: Literal["auto", "openai", "gemini"] = "auto"
    openai_model_fast: str = "gpt-5.6-luna"
    openai_model_balanced: str = "gpt-5.6-terra"
    openai_model_expert: str = "gpt-5.6-sol"
    gemini_model_fast: str = "gemini-flash-lite-latest"
    gemini_model_balanced: str = "gemini-flash-latest"
    gemini_model_expert: str = "gemini-flash-latest"
    gemini_model_critic: str = "gemini-flash-latest"
    gemini_model_vision: str = "gemini-flash-latest"
    computer_use_cost_mode: Literal["economy", "balanced", "quality"] = "economy"
    computer_use_local_perception_enabled: bool = True
    model_pricing_usd_per_million_tokens: dict[str, dict[str, float]] = Field(
        default_factory=dict
    )

    # -.-.-.-
    @field_validator("os_system", mode="before")
    @classmethod
    def normalize_os(cls, value: Any) -> Any:
        if value is None or value == "":
            return _platform_os()
        return str(value).strip().lower()

    # -.-.-.-
    @field_validator("assistant_name", mode="before")
    @classmethod
    def normalize_assistant_name(cls, value: Any) -> str:
        normalized = str(value or "").strip()
        return normalized or "Antonella"

    # -.-.-.-
    @field_validator(
        "user_name",
        "voice_name",
        "voice_style",
        "ui_color",
        "llm_url",
        "llm_model",
        "llm_provider",
        "openai_model_fast",
        "openai_model_balanced",
        "openai_model_expert",
        "gemini_model_fast",
        "gemini_model_balanced",
        "gemini_model_expert",
        "gemini_model_critic",
        "gemini_model_vision",
        mode="before",
    )
    @classmethod
    def normalize_string(cls, value: Any) -> str:
        return str(value or "").strip()

    # -.-.-.-
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return env_settings, init_settings, file_secret_settings


# -.-.-.-
def read_legacy_config(config_file: Path = CONFIG_FILE) -> dict[str, Any]:
    if not config_file.exists():
        return {}
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


# -.-.-.-
def write_legacy_config(data: dict[str, Any], config_file: Path = CONFIG_FILE) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(data, indent=4), encoding="utf-8")


# -.-.-.-
def load_settings(config_file: Path = CONFIG_FILE) -> AntonellaSettings:
    return AntonellaSettings(**read_legacy_config(config_file))


# -.-.-.-
def _unwrap_setting_value(value: Any) -> Any:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


# -.-.-.-
def _has_environment_override(field_name: str) -> bool:
    expected = f"ANTONELLA_{field_name}".lower()
    return any(key.lower() == expected for key in os.environ)


# -.-.-.-
def load_legacy_compatible_config(config_file: Path = CONFIG_FILE) -> dict[str, Any]:
    """Preserve the old sparse dict while applying explicit environment overrides."""
    data = read_legacy_config(config_file)
    settings = load_settings(config_file)

    for field_name in AntonellaSettings.model_fields:
        if not _has_environment_override(field_name):
            continue
        data[field_name] = _unwrap_setting_value(getattr(settings, field_name))

    return data


# -.-.-.-
def load_config(config_file: Path = CONFIG_FILE) -> dict[str, Any]:
    """Return the legacy dictionary with typed settings and env overrides applied."""
    data = read_legacy_config(config_file)
    settings = load_settings(config_file)

    data.update(
        {
            "os_system": settings.os_system,
            "assistant_name": settings.assistant_name,
            "user_name": settings.user_name,
            "voice_name": settings.voice_name,
            "voice_style": settings.voice_style,
            "morning_brief_enabled": settings.morning_brief_enabled,
            "plugins_enabled": settings.plugins_enabled,
            "ui_color": settings.ui_color,
            "llm_url": settings.llm_url,
            "llm_model": settings.llm_model,
            "llm_provider": settings.llm_provider,
            "model_provider_preference": settings.model_provider_preference,
            "openai_model_fast": settings.openai_model_fast,
            "openai_model_balanced": settings.openai_model_balanced,
            "openai_model_expert": settings.openai_model_expert,
            "gemini_model_fast": settings.gemini_model_fast,
            "gemini_model_balanced": settings.gemini_model_balanced,
            "gemini_model_expert": settings.gemini_model_expert,
            "gemini_model_critic": settings.gemini_model_critic,
            "gemini_model_vision": settings.gemini_model_vision,
            "computer_use_cost_mode": settings.computer_use_cost_mode,
            "computer_use_local_perception_enabled": (
                settings.computer_use_local_perception_enabled
            ),
            "model_pricing_usd_per_million_tokens": (
                settings.model_pricing_usd_per_million_tokens
            ),
        }
    )

    if settings.gemini_api_key is not None:
        data["gemini_api_key"] = settings.gemini_api_key.get_secret_value()

    if settings.openai_api_key is not None:
        data["openai_api_key"] = settings.openai_api_key.get_secret_value()

    return data


# -.-.-.-
def get_gemini_key(config_file: Path = CONFIG_FILE) -> str | None:
    secret = load_settings(config_file).gemini_api_key
    return secret.get_secret_value() if secret is not None else None


# -.-.-.-
def get_openai_key(config_file: Path = CONFIG_FILE) -> str | None:
    secret = load_settings(config_file).openai_api_key
    return secret.get_secret_value() if secret is not None else None
