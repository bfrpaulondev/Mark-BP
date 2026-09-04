"""Antonella dependency readiness checks.

Runtime package installation is intentionally forbidden. Dependencies are
installed only by the explicit, reproducible project setup process.
"""
from __future__ import annotations

import importlib.util
import platform
from typing import Callable


# Each entry: (import_name, install_profile)
_CORE: list[tuple[str, str]] = [
    ("psutil", "core"),
    ("PIL", "core"),
    ("sounddevice", "core"),
    ("numpy", "core"),
    ("requests", "core"),
    ("bs4", "core"),
    ("ddgs", "core"),
    ("pyautogui", "core"),
    ("pyperclip", "core"),
    ("pygetwindow", "core"),
    ("mss", "core"),
    ("cv2", "core"),
    ("send2trash", "core"),
    ("pptx", "core"),
    ("youtube_transcript_api", "core"),
    ("playwright", "core"),
]

_WINDOWS: list[tuple[str, str]] = [
    ("comtypes", "core"),
    ("pycaw", "core"),
    ("win10toast", "core"),
    ("pywinauto", "core"),
]

_STT: dict[str, list[tuple[str, str]]] = {
    "whisper": [("faster_whisper", "stt-whisper")],
    "vosk": [("vosk", "stt-vosk")],
}

_TTS: dict[str, list[tuple[str, str]]] = {
    "edgetts": [("edge_tts", "tts-edge"), ("miniaudio", "tts-edge")],
    "kokoro": [("kokoro", "tts-kokoro"), ("soundfile", "tts-kokoro")],
    "elevenlabs": [("miniaudio", "tts-elevenlabs")],
}


# -.-.-.-
def _available(module: str) -> bool:
    """Return True when the module can be resolved without importing it."""
    return importlib.util.find_spec(module) is not None


# -.-.-.-
def _required_modules(config: dict) -> list[tuple[str, str]]:
    stt = str(config.get("stt_engine", "whisper")).lower()
    tts = str(config.get("tts_engine", "edgetts")).lower()

    needed: list[tuple[str, str]] = list(_CORE)
    needed += _STT.get(stt, [])
    needed += _TTS.get(tts, [])
    if platform.system() == "Windows":
        needed += _WINDOWS

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for module, profile in needed:
        if module in seen:
            continue
        seen.add(module)
        unique.append((module, profile))
    return unique


# -.-.-.-
def missing_for_config(config: dict) -> list[tuple[str, str]]:
    """Return missing modules and the explicit installation profile for each one."""
    return [
        (module, profile)
        for module, profile in _required_modules(config)
        if not _available(module)
    ]


# -.-.-.-
def install_for_config(config: dict, log: Callable | None = None) -> None:
    """Compatibility entry point that now performs readiness checks only.

    The function keeps the legacy call contract but never installs packages or
    downloads browser binaries. Missing dependencies are reported with an
    explicit command that the user or deployment process can run deliberately.
    """
    missing = missing_for_config(config)
    if not missing:
        if log:
            log("SYS: All selected dependencies are already installed.")
        return

    profiles = sorted({profile for _, profile in missing if profile != "core"})
    modules = ", ".join(module for module, _ in missing)
    command = "uv sync --locked"
    if profiles:
        extras = " ".join(f"--extra {profile}" for profile in profiles)
        command = f"{command} {extras}"

    if log:
        log(f"ERR: Missing dependencies: {modules}")
        log(f"SYS: Runtime installation is disabled. Run explicitly: {command}")
