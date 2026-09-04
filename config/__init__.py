from __future__ import annotations

from pathlib import Path

from config.settings import (
    CONFIG_FILE,
    get_gemini_key as _get_gemini_key,
    get_openai_key as _get_openai_key,
    load_config,
)


_CONFIG_PATH = CONFIG_FILE


# -.-.-.-
def get_config() -> dict:
    return load_config(_CONFIG_PATH)


# -.-.-.-
def get_gemini_key() -> str | None:
    return _get_gemini_key(_CONFIG_PATH)


# -.-.-.-
def get_openai_key() -> str | None:
    return _get_openai_key(_CONFIG_PATH)


# -.-.-.-
def get_os() -> str:
    """Returns: 'windows' | 'mac' | 'linux'."""
    return get_config()["os_system"]


# -.-.-.-
def is_windows() -> bool:
    return get_os() == "windows"


# -.-.-.-
def is_mac() -> bool:
    return get_os() == "mac"


# -.-.-.-
def is_linux() -> bool:
    return get_os() == "linux"
