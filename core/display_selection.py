from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


# -.-.-.-
def monitor_contains_point(monitor: Mapping[str, Any], x: int, y: int) -> bool:
    left = int(monitor.get("left", 0))
    top = int(monitor.get("top", 0))
    width = int(monitor.get("width", 0))
    height = int(monitor.get("height", 0))
    return left <= x < left + width and top <= y < top + height


# -.-.-.-
def select_monitor(
    monitors: Sequence[Mapping[str, Any]],
    *,
    point: tuple[int, int] | None = None,
    hint: int | str | None = None,
) -> Mapping[str, Any]:
    if not monitors:
        raise ValueError("No monitors available")

    if hint is not None:
        normalized = str(hint).strip().lower()
        if normalized == "all":
            return monitors[0]
        if normalized.isdigit():
            index = int(normalized)
            if 1 <= index < len(monitors):
                return monitors[index]

    if point is not None:
        x, y = point
        for monitor in monitors[1:]:
            if monitor_contains_point(monitor, x, y):
                return monitor

    return monitors[1] if len(monitors) > 1 else monitors[0]
