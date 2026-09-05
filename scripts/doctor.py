from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import TextIO


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import get_config, get_gemini_key, get_openai_key
from core.installer import missing_for_config


SUPPORTED_PYTHON = {(3, 11), (3, 12)}
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
ANTONELLA_ENTRYPOINT = BASE_DIR / "antonella.py"
ANTONELLA_UI = BASE_DIR / "ui" / "__init__.py"
COMPUTER_USE_PLUGIN = BASE_DIR / "plugins" / "realtime_computer_use.py"
WINDOWS_UIA_PLUGIN = BASE_DIR / "plugins" / "windows_ui_automation.py"


# -.-.-.-
def _write(stream: TextIO, status: str, message: str) -> None:
    stream.write(f"[{status}] {message}\n")


# -.-.-.-
def _probe_runtime(code: str) -> bool:
    """Isolate native imports and device checks; never print child output or secrets."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


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
        gemini_key = get_gemini_key()
        openai_key = get_openai_key()
        _write(stream, "PASS", "Configuration loaded through the typed settings contract.")
    except Exception as exc:
        failures += 1
        _write(stream, "FAIL", f"Configuration could not be loaded: {type(exc).__name__}.")
        config = {}
        gemini_key = openai_key = None

    if gemini_key:
        _write(stream, "PASS", "Gemini API key is configured; connectivity is not tested.")
    else:
        failures += 1
        _write(
            stream,
            "FAIL",
            "Gemini API key is missing. Set ANTONELLA_GEMINI_API_KEY or configure config/api_keys.json.",
        )

    if openai_key:
        mode = str(config.get("computer_use_cost_mode") or "economy")
        fast_model = str(config.get("openai_model_fast") or "gpt-5.6-luna")
        _write(
            stream,
            "PASS",
            f"Optional OpenAI planner is configured (Computer Use mode={mode}, economy model={fast_model}).",
        )
    else:
        _write(
            stream,
            "INFO",
            "OpenAI planner is not configured; Realtime Computer Use will use the Gemini fallback.",
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

    if COMPUTER_USE_PLUGIN.is_file() and WINDOWS_UIA_PLUGIN.is_file():
        _write(
            stream,
            "PASS",
            "Cost-aware desktop stack is present (Windows UI Automation → Realtime Computer Use fallback).",
        )
    else:
        failures += 1
        _write(stream, "FAIL", "Cost-aware desktop plugins are incomplete.")

    # Gemini Live owns audio in the canonical entrypoint, not the legacy STT/TTS adapters.
    missing = missing_for_config({**config, "stt_engine": "live", "tts_engine": "live"})
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

    for label, code in (
        ("Native audio/GUI/desktop imports", "import sounddevice; import PyQt6.QtWidgets; import pyautogui"),
        ("Default microphone and speaker", "import sounddevice as sd; sd.query_devices(kind='input'); sd.query_devices(kind='output')"),
    ):
        if _probe_runtime(code):
            _write(stream, "PASS", f"{label} passed.")
        else:
            failures += 1
            _write(stream, "FAIL", f"{label} failed or timed out. Check native libraries, desktop session and audio devices.")

    if _probe_runtime(
        "from pathlib import Path; from playwright.sync_api import sync_playwright; "
        "p = sync_playwright().start(); exists = Path(p.chromium.executable_path).is_file(); "
        "p.stop(); raise SystemExit(0 if exists else 1)"
    ):
        _write(stream, "PASS", "Playwright Chromium executable is present; browser launch is not tested.")
    else:
        _write(stream, "WARN", "Playwright Chromium could not be found. Run: uv run playwright install chromium")

    _write(stream, "INFO", "GUI rendering, audio recording/playback, provider calls and real desktop actions still require manual smoke tests.")

    if failures:
        _write(stream, "RESULT", f"Antonella is not ready for smoke testing ({failures} blocking check(s)).")
        return 1

    _write(stream, "RESULT", "Antonella is ready for a local smoke test. Run: uv run python antonella.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_doctor())
