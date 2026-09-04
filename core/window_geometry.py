from __future__ import annotations

import platform
from collections.abc import Mapping, Sequence
from typing import Any


# -.-.-.-
def normalize_rect(rect: Mapping[str, Any]) -> dict[str, int] | None:
    try:
        left = int(rect.get("left", 0))
        top = int(rect.get("top", 0))
        width = int(rect.get("width", 0))
        height = int(rect.get("height", 0))
    except (TypeError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None
    return {"left": left, "top": top, "width": width, "height": height}


# -.-.-.-
def intersect_rect(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, int] | None:
    a = normalize_rect(first)
    b = normalize_rect(second)
    if a is None or b is None:
        return None

    left = max(a["left"], b["left"])
    top = max(a["top"], b["top"])
    right = min(a["left"] + a["width"], b["left"] + b["width"])
    bottom = min(a["top"] + a["height"], b["top"] + b["height"])
    if right <= left or bottom <= top:
        return None

    return {
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top,
    }


# -.-.-.-
def rect_area(rect: Mapping[str, Any] | None) -> int:
    normalized = normalize_rect(rect or {})
    if normalized is None:
        return 0
    return normalized["width"] * normalized["height"]


# -.-.-.-
def monitor_index_for_rect(
    monitors: Sequence[Mapping[str, Any]],
    rect: Mapping[str, Any],
) -> int:
    """Choose the real monitor containing the greatest visible portion of rect."""
    if len(monitors) <= 1:
        return 0

    best_index = 1
    best_area = -1
    for index, monitor in enumerate(monitors[1:], start=1):
        area = rect_area(intersect_rect(rect, monitor))
        if area > best_area:
            best_index = index
            best_area = area
    return best_index


# -.-.-.-
def clip_rect_to_desktop(
    rect: Mapping[str, Any],
    monitors: Sequence[Mapping[str, Any]],
) -> dict[str, int] | None:
    normalized = normalize_rect(rect)
    if normalized is None:
        return None
    if not monitors:
        return normalized

    combined = normalize_rect(monitors[0])
    if combined is None:
        return normalized
    return intersect_rect(normalized, combined)


# -.-.-.-
def resolve_window_region(
    title_fragment: str,
    monitors: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, int], int] | None:
    """Resolve a visible Windows window to an MSS-safe region without taking a screenshot."""
    title_fragment = str(title_fragment or "").strip()
    if not title_fragment or platform.system() != "Windows":
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    user32 = ctypes.windll.user32
    needle = title_fragment.casefold()
    foreground = user32.GetForegroundWindow()
    candidates: list[tuple[int, int, dict[str, int]]] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _collect(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if not title or needle not in title.casefold():
                return True

            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True

            raw = {
                "left": int(rect.left),
                "top": int(rect.top),
                "width": int(rect.right - rect.left),
                "height": int(rect.bottom - rect.top),
            }
            clipped = clip_rect_to_desktop(raw, monitors)
            if clipped is None or clipped["width"] < 120 or clipped["height"] < 80:
                return True

            foreground_score = 1 if hwnd == foreground else 0
            candidates.append((foreground_score, rect_area(clipped), clipped))
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(EnumWindowsProc(_collect), 0)
    except Exception:
        return None

    if not candidates:
        return None

    _foreground_score, _area, region = max(candidates, key=lambda item: (item[0], item[1]))
    return region, monitor_index_for_rect(monitors, region)


# -.-.-.-
def region_savings_ratio(
    region: Mapping[str, Any],
    monitor: Mapping[str, Any],
) -> float:
    """Fraction of monitor pixels avoided by window-scoped capture, from 0 to <1."""
    monitor_pixels = rect_area(monitor)
    if monitor_pixels <= 0:
        return 0.0
    region_pixels = min(rect_area(region), monitor_pixels)
    return max(0.0, min(0.999, 1.0 - (region_pixels / monitor_pixels)))
