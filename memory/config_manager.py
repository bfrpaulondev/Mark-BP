from __future__ import annotations

import sys
from pathlib import Path

from config.settings import load_config, read_legacy_config, write_legacy_config


# -.-.-.-
def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"


# -.-.-.-
def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


# -.-.-.-
def config_exists() -> bool:
    return CONFIG_FILE.exists()


# -.-.-.-
def _load_persisted_config() -> dict:
    return read_legacy_config(CONFIG_FILE)


# -.-.-.-
def _save_persisted_config(data: dict) -> None:
    ensure_config_dir()
    write_legacy_config(data, CONFIG_FILE)


# -.-.-.-
def save_api_keys(gemini_api_key: str) -> None:
    data = _load_persisted_config()
    data["gemini_api_key"] = gemini_api_key.strip()
    _save_persisted_config(data)


# -.-.-.-
def load_api_keys() -> dict:
    return load_config(CONFIG_FILE)


# -.-.-.-
def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")


# -.-.-.-
def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


# -.-.-.-
def get_assistant_name() -> str:
    return load_api_keys().get("assistant_name", "JARVIS") or "JARVIS"


# -.-.-.-
def get_user_name() -> str:
    return load_api_keys().get("user_name", "")


# -.-.-.-
def save_assistant_config(assistant_name: str, user_name: str) -> None:
    data = _load_persisted_config()
    data["assistant_name"] = assistant_name.strip() or "JARVIS"
    data["user_name"] = user_name.strip()
    _save_persisted_config(data)


# -.-.-.-
def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


# -.-.-.-
def save_brief_enabled(enabled: bool) -> None:
    data = _load_persisted_config()
    data["morning_brief_enabled"] = enabled
    _save_persisted_config(data)


# -.-.-.-
def get_plugin_enabled(plugin_name: str) -> bool:
    return load_api_keys().get("plugins_enabled", {}).get(plugin_name, True)


# -.-.-.-
def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    data = _load_persisted_config()
    plugins_cfg = data.get("plugins_enabled")
    if not isinstance(plugins_cfg, dict):
        plugins_cfg = {}
    plugins_cfg[plugin_name] = enabled
    data["plugins_enabled"] = plugins_cfg
    _save_persisted_config(data)
