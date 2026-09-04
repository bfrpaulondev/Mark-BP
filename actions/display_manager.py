from __future__ import annotations

import json
import platform
from typing import Any

from core.display_selection import describe_monitors, select_monitor, selected_monitor_index


# -.-.-.-
def _active_screen_point() -> tuple[int, int] | None:
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 0 and height > 0:
                return rect.left + width // 2, rect.top + height // 2

        cursor = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(cursor)):
            return int(cursor.x), int(cursor.y)
    except Exception:
        return None
    return None


# -.-.-.-
def display_manager(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "list").strip().lower()

    try:
        import mss
    except ImportError:
        return json.dumps(
            {"ok": False, "error": "Display manager requires mss from the locked install."},
            ensure_ascii=False,
        )

    try:
        with mss.mss() as sct:
            monitors = list(sct.monitors)
            active_point = _active_screen_point()

            if action in {"list", "status"}:
                displays = describe_monitors(monitors, active_point=active_point)
                return json.dumps(
                    {
                        "ok": True,
                        "count": len(displays),
                        "displays": displays,
                        "combined": dict(monitors[0]) if monitors else None,
                    },
                    ensure_ascii=False,
                )

            if action == "resolve":
                hint: Any = params.get("monitor")
                target = select_monitor(monitors, point=active_point, hint=hint)
                index = selected_monitor_index(monitors, target)
                return json.dumps(
                    {
                        "ok": True,
                        "requested": hint,
                        "resolved_index": index,
                        "monitor": dict(target),
                    },
                    ensure_ascii=False,
                )

            return json.dumps(
                {"ok": False, "error": "Use action=list or resolve."},
                ensure_ascii=False,
            )
    except Exception as exc:
        if player:
            try:
                player.write_log(f"SYS: Display manager · {exc}")
            except Exception:
                pass
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
