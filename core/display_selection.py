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
def normalize_monitor_hint(value: int | str | None) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None

    normalized = str(value).strip().lower()
    if not normalized or normalized in {"active", "foreground", "current", "auto"}:
        return None
    if normalized in {"all", "combined", "desktop"}:
        return "all"
    if normalized.startswith("monitor "):
        normalized = normalized.removeprefix("monitor ").strip()
    if normalized.startswith("screen "):
        normalized = normalized.removeprefix("screen ").strip()
    if normalized.isdigit():
        return int(normalized)
    return None


# -.-.-.-
def select_monitor(
    monitors: Sequence[Mapping[str, Any]],
    *,
    point: tuple[int, int] | None = None,
    hint: int | str | None = None,
) -> Mapping[str, Any]:
    if not monitors:
        raise ValueError("No monitors available")

    normalized_hint = normalize_monitor_hint(hint)
    if normalized_hint == "all":
        return monitors[0]
    if isinstance(normalized_hint, int) and 1 <= normalized_hint < len(monitors):
        return monitors[normalized_hint]

    if point is not None:
        x, y = point
        for monitor in monitors[1:]:
            if monitor_contains_point(monitor, x, y):
                return monitor

    return monitors[1] if len(monitors) > 1 else monitors[0]


# -.-.-.-
def selected_monitor_index(
    monitors: Sequence[Mapping[str, Any]],
    monitor: Mapping[str, Any],
) -> int:
    for index, candidate in enumerate(monitors):
        if candidate == monitor:
            return index
    return 0


# -.-.-.-
def describe_monitors(
    monitors: Sequence[Mapping[str, Any]],
    *,
    active_point: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, monitor in enumerate(monitors):
        if index == 0:
            continue
        left = int(monitor.get("left", 0))
        top = int(monitor.get("top", 0))
        width = int(monitor.get("width", 0))
        height = int(monitor.get("height", 0))
        is_active = bool(
            active_point
            and monitor_contains_point(monitor, active_point[0], active_point[1])
        )
        output.append(
            {
                "index": index,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "right": left + width,
                "bottom": top + height,
                "active": is_active,
            }
        )
    return output
