from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import get_config, get_gemini_key
from core.installer import missing_for_config


SUPPORTED_PYTHON = {(3, 11), (3, 12)}
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
ANTONELLA_ENTRYPOINT = BASE_DIR / "antonella.py"
ANTONELLA_UI = BASE_DIR / "ui" / "__init__.py"


# -.-.-.-
def _write(stream: TextIO, status: str, message: str) -> None:
    stream.write(f"[{status}] {message}\n")


# -.-.-.-
def run_doctor(stream: TextIO = sys.stdout) -> int:
    """Check whether the current checkout is ready for a local Antonella smoke test."""
    failures = 0

    python_version = (sys.version_info.major, sys.version_info.minor)
    if python_version in SUPPORTED_PYTHON:
        _write(stream, "PASS", f"Python {python_version[0]}.{python_version[1]} is supported.")
    else:
        failures += 1
        _write(
            stream,
            "FAIL",
            f"Python {python_version[0]}.{python_version[1]} is unsupported. Use Python 3.11 or 3.12.",
        )

    try:
        config = get_config()
        _write(stream, "PASS", "Configuration loaded through the typed settings contract.")
    except Exception as exc:
        failures += 1
        _write(stream, "FAIL", f"Configuration could not be loaded: {type(exc).__name__}.")
        config = {}

    if get_gemini_key():
        _write(stream, "PASS", "Gemini API key is configured.")
    else:
        failures += 1
        _write(
            stream,
            "FAIL",
            "Gemini API key is missing. Set ANTONELLA_GEMINI_API_KEY or configure config/api_keys.json.",
        )

    if PROMPT_PATH.is_file():
        _write(stream, "PASS", "Antonella system prompt is present.")
    else:
        failures += 1
        _write(stream, "FAIL", "core/prompt.txt is missing.")

    if ANTONELLA_ENTRYPOINT.is_file() and ANTONELLA_UI.is_file():
        voice_name = str(config.get("voice_name") or "Kore")
        _write(stream, "PASS", f"Antonella desktop UI and voice profile are present (voice={voice_name}).")
    else:
        failures += 1
        _write(stream, "FAIL", "Antonella desktop UI or antonella.py entrypoint is missing.")

    missing = missing_for_config(config)
    if not missing:
        _write(stream, "PASS", "Selected runtime dependencies are available.")
    else:
        failures += 1
        modules = ", ".join(module for module, _ in missing)
        profiles = sorted({profile for _, profile in missing if profile != "core"})
        command = "uv sync --locked"
        if profiles:
            command += " " + " ".join(f"--extra {profile}" for profile in profiles)
        _write(stream, "FAIL", f"Missing runtime dependencies: {modules}.")
        _write(stream, "INFO", f"Install explicitly with: {command}")

    if failures:
        _write(stream, "RESULT", f"Antonella is not ready for smoke testing ({failures} blocking check(s)).")
        return 1

    _write(stream, "RESULT", "Antonella is ready for a local smoke test. Run: uv run python antonella.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_doctor())
