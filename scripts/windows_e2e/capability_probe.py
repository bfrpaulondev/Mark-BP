"""Windows physical E2E capability probe (ANT-275 C2).

Detects technical capabilities of the current machine WITHOUT collecting
PII: booleans, versions and monitor geometry only. Never reports user
names, full home paths or installed-software listings.

Standard library only; optional integrations (pycaw, pywinauto, ...)
are reported as availability flags, never imported at module level.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _windows_monitors() -> list[dict[str, Any]]:
    """Enumerate monitors via user32 (geometry only, no device names)."""
    if sys.platform != "win32":
        return []

    monitors: list[dict[str, Any]] = []

    def _callback(_hdc: Any, _rect: Any, lparam: Any, hmonitor: Any) -> int:
        info = ctypes.c_char(0)  # placeholder to keep ctypes callback shape simple
        del info, lparam
        # MONITORINFO via GetMonitorInfoW (geometry only)
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

        user32 = ctypes.windll.user32
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(mi)):
            monitors.append(
                {
                    "primary": bool(mi.dwFlags & 1),
                    "x": int(mi.rcMonitor.left),
                    "y": int(mi.rcMonitor.top),
                    "width": int(mi.rcMonitor.right - mi.rcMonitor.left),
                    "height": int(mi.rcMonitor.bottom - mi.rcMonitor.top),
                }
            )
        return 1

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.c_double
    )
    try:
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_callback), 0)
    except Exception:
        return []
    return monitors


def _browser_available(browser: str) -> bool:
    """True when the browser executable exists at a standard location.

    Only a boolean is reported: full paths contain the user name (PII).
    """
    if sys.platform != "win32":
        return False
    candidates = {
        "chrome": ("ProgramFiles", "Google/Chrome/Application/chrome.exe"),
        "edge": ("ProgramFiles(x86)", "Microsoft/Edge/Application/msedge.exe"),
    }
    if browser not in candidates:
        return False
    env_var, relative = candidates[browser]
    base = os.environ.get(env_var)
    if not base:
        return False
    return (Path(base) / relative).exists()


def probe() -> dict[str, Any]:
    """Collect machine capabilities; technical metadata only, no PII."""
    monitors = _windows_monitors()
    return {
        "platform": sys.platform,
        "windows_version": platform.version() if sys.platform == "win32" else "",
        "python_version": platform.python_version(),
        "monitor_count": len(monitors),
        "monitors": monitors,
        "negative_coordinates": any(m["x"] < 0 or m["y"] < 0 for m in monitors),
        "primary_resolution": next(
            ({"width": m["width"], "height": m["height"]} for m in monitors if m["primary"]),
            None,
        ),
        "chrome_available": _browser_available("chrome"),
        "edge_available": _browser_available("edge"),
        "microphone_available": _module_available("sounddevice"),
        # Optional integrations are flattened to the top level so the
        # matrix requirements and the runner can address them directly.
        **{
            name.lower(): _module_available(name)
            for name in ("pywinauto", "pycaw", "wmi", "mss", "playwright", "PyQt6", "sounddevice")
        },
        # CDP is opt-in by explicit configuration only.
        "cdp_available": bool(os.environ.get("ANTONELLA_E2E_CDP")),
    }


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
