"""Windows physical E2E capability probe (ANT-275 C2).

Detects technical capabilities of the current machine WITHOUT collecting
PII: booleans, versions and monitor geometry only. Never reports user
names, full home paths or installed-software listings.

Optional integrations are reported as availability flags. Hardware flags
such as monitor count and microphone availability are based on an actual
probe, not merely on an installed Python package.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


# -.-.-.-
def _package_version(distribution: str) -> str | None:
    """Return package version only; never expose install paths or metadata."""
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None
    except Exception:
        return "unknown"


# -.-.-.-
def _known_package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in (
        "pywinauto",
        "pycaw",
        "comtypes",
        "PyQt6",
        "playwright",
        "sounddevice",
        "WMI",
    ):
        version = _package_version(distribution)
        if version is not None:
            versions[distribution.lower()] = version
    return versions


def _windows_monitors() -> list[dict[str, Any]]:
    """Enumerate monitors via user32 (geometry only, no device names)."""
    if sys.platform != "win32":
        return []

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", ctypes.c_ulong),
        ]

    monitors: list[dict[str, Any]] = []
    user32 = ctypes.windll.user32

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(RECT),
        ctypes.c_void_p,
    )

    def _callback(
        hmonitor: int,
        _hdc: int,
        _rect: ctypes.POINTER(RECT),
        _lparam: int,
    ) -> int:
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            monitors.append(
                {
                    "primary": bool(info.dwFlags & 1),
                    "x": int(info.rcMonitor.left),
                    "y": int(info.rcMonitor.top),
                    "width": int(info.rcMonitor.right - info.rcMonitor.left),
                    "height": int(info.rcMonitor.bottom - info.rcMonitor.top),
                }
            )
        return 1

    try:
        callback = MONITORENUMPROC(_callback)
        ok = user32.EnumDisplayMonitors(0, 0, callback, 0)
        if not ok:
            return []
    except Exception:
        return []
    return monitors


def _browser_available(browser: str) -> bool:
    """Return only a boolean; candidate paths are never emitted."""
    if sys.platform != "win32":
        return False

    candidates: dict[str, tuple[tuple[str, str], ...]] = {
        "chrome": (
            ("ProgramFiles", "Google/Chrome/Application/chrome.exe"),
            ("ProgramFiles(x86)", "Google/Chrome/Application/chrome.exe"),
            ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
        ),
        "edge": (
            ("ProgramFiles(x86)", "Microsoft/Edge/Application/msedge.exe"),
            ("ProgramFiles", "Microsoft/Edge/Application/msedge.exe"),
        ),
    }
    for env_var, relative in candidates.get(browser, ()):
        base = os.environ.get(env_var)
        if base and (Path(base) / relative).exists():
            return True
    return False


def _microphone_available() -> bool:
    """Probe for a usable default input without exposing device metadata."""
    try:
        import sounddevice as sd

        info = sd.query_devices(kind="input")
        if isinstance(info, dict):
            return int(info.get("max_input_channels") or 0) > 0
        max_channels = getattr(info, "max_input_channels", 0)
        return int(max_channels or 0) > 0
    except Exception:
        return False


def probe() -> dict[str, Any]:
    """Collect machine capabilities; technical metadata only, no PII."""
    monitors = _windows_monitors()
    optional = {
        name.lower(): _module_available(name)
        for name in (
            "pywinauto",
            "pycaw",
            "wmi",
            "mss",
            "playwright",
            "PyQt6",
            "sounddevice",
        )
    }
    return {
        "platform": sys.platform,
        "windows_version": platform.version() if sys.platform == "win32" else "",
        "python_version": platform.python_version(),
        "package_versions": _known_package_versions(),
        "monitor_count": len(monitors),
        "monitors": monitors,
        "negative_coordinates": any(
            monitor["x"] < 0 or monitor["y"] < 0 for monitor in monitors
        ),
        "primary_resolution": next(
            (
                {"width": monitor["width"], "height": monitor["height"]}
                for monitor in monitors
                if monitor["primary"]
            ),
            None,
        ),
        "chrome_available": _browser_available("chrome"),
        "edge_available": _browser_available("edge"),
        "microphone_available": _microphone_available(),
        **optional,
        "cdp_available": bool(os.environ.get("ANTONELLA_E2E_CDP")),
    }


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
