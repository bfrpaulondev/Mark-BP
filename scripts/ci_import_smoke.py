"""Windows CI import smoke (ANT-273).

Imports every project module that CI can realistically import without the
heavy runtime dependencies (PyQt6, pywinauto, psutil, ... are NOT installed
in the CI environment). Only known optional/runtime dependency roots may be
skipped. Unknown missing imports fail the job so local import typos are not
silently misclassified as third-party dependencies.

Usage: python scripts/ci_import_smoke.py
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROJECT_TOP_LEVEL = {
    "core",
    "actions",
    "config",
    "dashboard",
    "memory",
    "plugins",
    "ui",
    "scripts",
    "docs",
}

# Import roots for dependencies intentionally omitted from the minimal CI
# environment. Keep this list explicit: an unknown ModuleNotFoundError should
# fail closed instead of hiding a typo in a project-local import.
ALLOWED_MISSING_IMPORT_ROOTS = {
    "PIL",
    "PyQt6",
    "bs4",
    "comtypes",
    "cryptography",
    "cv2",
    "ddgs",
    "edge_tts",
    "fastapi",
    "faster_whisper",
    "google",
    "kokoro",
    "miniaudio",
    "mss",
    "multipart",
    "numpy",
    "playwright",
    "pptx",
    "psutil",
    "pyautogui",
    "pycaw",
    "pygetwindow",
    "pyperclip",
    "pythoncom",
    "qrcode",
    "requests",
    "send2trash",
    "sounddevice",
    "soundfile",
    "uvicorn",
    "vosk",
    "win10toast",
    "win32api",
    "win32com",
    "win32con",
    "win32gui",
    "win32process",
    "win32security",
    "win32service",
    "win32serviceutil",
    "youtube_transcript_api",
}

# Packages scanned for importable modules. plugins/ is excluded on purpose:
# drop-in plugin files are loaded by the runtime's own plugin loader, not by
# the import system.
SMOKE_PACKAGES = ("core", "actions", "config", "dashboard", "memory", "scripts")

# Qt-free module kept outside the ui package import path (ui/__init__ needs Qt).
EXTRA_FILES = (("ui", "runtime_state.py"),)


def _classify_import_error(exc: BaseException) -> str | None:
    """Return 'missing-dep' only for an explicitly known external dependency."""
    if isinstance(exc, ModuleNotFoundError) and exc.name:
        top = exc.name.split(".", 1)[0]
        if top in PROJECT_TOP_LEVEL:
            return None
        if top in ALLOWED_MISSING_IMPORT_ROOTS:
            return "missing-dep"
    return None


def _collect_modules() -> list[str]:
    names: list[str] = []
    for package in SMOKE_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            if path.name == "__init__.py":
                continue
            relative = path.relative_to(ROOT)
            parts = relative.with_suffix("").parts
            # Skip files that cannot be addressed as dotted module names
            # (e.g. names with spaces or dashes).
            if not all(part.isidentifier() for part in parts):
                continue
            names.append(".".join(parts))
    return names


def _load_extra_files() -> list[tuple[str, BaseException | None]]:
    results: list[tuple[str, BaseException | None]] = []
    for package, filename in EXTRA_FILES:
        path = ROOT / package / filename
        if not path.exists():
            # File lives on an unmerged branch; nothing to smoke here yet.
            continue
        spec = importlib.util.spec_from_file_location(f"antonella_smoke_{path.stem}", path)
        if spec is None or spec.loader is None:
            results.append((str(path.relative_to(ROOT)), RuntimeError("Could not create import spec.")))
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            results.append((str(path.relative_to(ROOT)), None))
        except BaseException as exc:  # noqa: BLE001 - smoke must classify everything
            if _classify_import_error(exc) == "missing-dep":
                results.append((str(path.relative_to(ROOT)), None))
            else:
                results.append((str(path.relative_to(ROOT)), exc))
        finally:
            sys.modules.pop(spec.name, None)
    return results


def main() -> int:
    imported: list[str] = []
    skipped: list[tuple[str, str]] = []
    failures: list[tuple[str, BaseException]] = []

    for module_name in _collect_modules():
        try:
            importlib.import_module(module_name)
            imported.append(module_name)
        except BaseException as exc:  # noqa: BLE001
            if _classify_import_error(exc) == "missing-dep":
                skipped.append((module_name, str(exc)))
            else:
                failures.append((module_name, exc))

    for name, exc in _load_extra_files():
        if exc is None:
            imported.append(name)
        else:
            failures.append((name, exc))

    print(f"import smoke: {len(imported)} imported, {len(skipped)} skipped (known missing dep)")
    for name, reason in skipped:
        print(f"  SKIP {name}: {reason}")
    for name, exc in failures:
        print(f"  FAIL {name}: {type(exc).__name__}: {exc}")
        traceback.print_exception(exc, file=sys.stderr)

    if failures:
        print(f"import smoke: {len(failures)} FAILURE(S)")
        return 1
    print("import smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
