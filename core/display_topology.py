from __future__ import annotations

import ctypes
import hashlib
import json
import platform
from contextlib import contextmanager
from ctypes import wintypes
from collections.abc import Mapping, Sequence
from typing import Any, Iterator


_DEFAULT_DPI = 96
_PRIMARY_FLAG = 0x00000001
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


# -.-.-.-
def _rect_dict(left: int, top: int, right: int, bottom: int) -> dict[str, int]:
    return {
        "left": int(left),
        "top": int(top),
        "width": max(0, int(right) - int(left)),
        "height": max(0, int(bottom) - int(top)),
    }


# -.-.-.-
def _rect_tuple(rect: Mapping[str, Any]) -> tuple[int, int, int, int]:
    left = int(rect.get("left", 0))
    top = int(rect.get("top", 0))
    width = int(rect.get("width", 0))
    height = int(rect.get("height", 0))
    return left, top, width, height


# -.-.-.-
def _intersection_area(first: Mapping[str, Any], second: Mapping[str, Any]) -> int:
    a_left, a_top, a_width, a_height = _rect_tuple(first)
    b_left, b_top, b_width, b_height = _rect_tuple(second)
    left = max(a_left, b_left)
    top = max(a_top, b_top)
    right = min(a_left + a_width, b_left + b_width)
    bottom = min(a_top + a_height, b_top + b_height)
    return max(0, right - left) * max(0, bottom - top)


# -.-.-.-
@contextmanager
def per_monitor_dpi_context() -> Iterator[bool]:
    """Temporarily request physical per-monitor coordinates on the current Windows thread."""
    if platform.system() != "Windows":
        yield False
        return

    try:
        user32 = ctypes.windll.user32
        setter = getattr(user32, "SetThreadDpiAwarenessContext", None)
        if setter is None:
            yield False
            return
        setter.argtypes = [ctypes.c_void_p]
        setter.restype = ctypes.c_void_p
        requested = ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        previous = setter(requested)
    except Exception:
        yield False
        return

    try:
        yield bool(previous)
    finally:
        if previous:
            try:
                setter(previous)
            except Exception:
                pass


# -.-.-.-
def window_dpi(hwnd: int) -> tuple[int, int]:
    if platform.system() != "Windows" or not hwnd:
        return _DEFAULT_DPI, _DEFAULT_DPI
    try:
        user32 = ctypes.windll.user32
        getter = getattr(user32, "GetDpiForWindow", None)
        if getter is None:
            return _DEFAULT_DPI, _DEFAULT_DPI
        getter.argtypes = [wintypes.HWND]
        getter.restype = wintypes.UINT
        with per_monitor_dpi_context():
            dpi = int(getter(wintypes.HWND(int(hwnd))) or _DEFAULT_DPI)
        return dpi, dpi
    except Exception:
        return _DEFAULT_DPI, _DEFAULT_DPI


# -.-.-.-
def foreground_window_rect() -> tuple[int, int, int, int, int] | None:
    """Return foreground HWND and physical rect as (hwnd,left,top,right,bottom)."""
    if platform.system() != "Windows":
        return None
    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        with per_monitor_dpi_context():
            hwnd = int(user32.GetForegroundWindow() or 0)
            if not hwnd:
                return None
            rect = wintypes.RECT()
            if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
                return None
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None
        return hwnd, int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    except Exception:
        return None


# -.-.-.-
def active_screen_point() -> tuple[int, int] | None:
    foreground = foreground_window_rect()
    if foreground is not None:
        _hwnd, left, top, right, bottom = foreground
        return left + (right - left) // 2, top + (bottom - top) // 2

    if platform.system() != "Windows":
        return None
    try:
        point = wintypes.POINT()
        with per_monitor_dpi_context():
            if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
                return int(point.x), int(point.y)
    except Exception:
        pass
    return None


# -.-.-.-
def _monitor_dpi(hmonitor: int) -> tuple[int, int]:
    if platform.system() != "Windows" or not hmonitor:
        return _DEFAULT_DPI, _DEFAULT_DPI
    try:
        hmonitor_type = getattr(wintypes, "HMONITOR", wintypes.HANDLE)
        shcore = ctypes.windll.shcore
        getter = shcore.GetDpiForMonitor
        getter.argtypes = [hmonitor_type, ctypes.c_int, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)]
        getter.restype = ctypes.c_long
        dpi_x = wintypes.UINT(_DEFAULT_DPI)
        dpi_y = wintypes.UINT(_DEFAULT_DPI)
        if getter(hmonitor_type(int(hmonitor)), 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
            return max(1, int(dpi_x.value)), max(1, int(dpi_y.value))
    except Exception:
        pass
    return _DEFAULT_DPI, _DEFAULT_DPI


# -.-.-.-
def windows_monitor_metadata() -> list[dict[str, Any]]:
    """Enumerate physical Windows monitor rectangles, primary flag, device name and effective DPI."""
    if platform.system() != "Windows":
        return []

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    try:
        user32 = ctypes.windll.user32
        hmonitor_type = getattr(wintypes, "HMONITOR", wintypes.HANDLE)
        hdc_type = getattr(wintypes, "HDC", wintypes.HANDLE)
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            hmonitor_type,
            hdc_type,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )
        results: list[dict[str, Any]] = []

        def _collect(hmonitor, _hdc, rect_ptr, _lparam):
            try:
                info = MONITORINFOEXW()
                info.cbSize = ctypes.sizeof(MONITORINFOEXW)
                if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                    return True
                rect = info.rcMonitor if info.rcMonitor.right > info.rcMonitor.left else rect_ptr.contents
                geometry = _rect_dict(rect.left, rect.top, rect.right, rect.bottom)
                dpi_x, dpi_y = _monitor_dpi(int(hmonitor))
                results.append(
                    {
                        **geometry,
                        "device": str(info.szDevice or "")[:64],
                        "primary": bool(info.dwFlags & _PRIMARY_FLAG),
                        "dpi_x": dpi_x,
                        "dpi_y": dpi_y,
                        "scale_x": round(dpi_x / _DEFAULT_DPI, 4),
                        "scale_y": round(dpi_y / _DEFAULT_DPI, 4),
                    }
                )
            except Exception:
                pass
            return True

        callback = callback_type(_collect)
        with per_monitor_dpi_context():
            user32.EnumDisplayMonitors(0, None, callback, 0)
        return results
    except Exception:
        return []


# -.-.-.-
def match_monitor_metadata(
    monitors: Sequence[Mapping[str, Any]],
    metadata: Sequence[Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Match MSS real-monitor entries to Windows metadata without assuming enumeration order."""
    matched: dict[int, dict[str, Any]] = {}
    unused = set(range(len(metadata)))

    for monitor_index, monitor in enumerate(monitors):
        if monitor_index == 0:
            continue
        exact = None
        monitor_rect = _rect_tuple(monitor)
        for meta_index in list(unused):
            if _rect_tuple(metadata[meta_index]) == monitor_rect:
                exact = meta_index
                break
        if exact is None and unused:
            exact = max(unused, key=lambda idx: _intersection_area(monitor, metadata[idx]))
            if _intersection_area(monitor, metadata[exact]) <= 0:
                exact = None
        if exact is not None:
            matched[monitor_index] = dict(metadata[exact])
            unused.discard(exact)
    return matched


# -.-.-.-
def _metadata_signature(metadata: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    entries = [
        {
            "left": _rect_tuple(item)[0],
            "top": _rect_tuple(item)[1],
            "width": _rect_tuple(item)[2],
            "height": _rect_tuple(item)[3],
            "device": str(item.get("device") or ""),
            "primary": bool(item.get("primary", False)),
            "dpi_x": int(item.get("dpi_x") or _DEFAULT_DPI),
            "dpi_y": int(item.get("dpi_y") or _DEFAULT_DPI),
        }
        for item in metadata
    ]
    return sorted(entries, key=lambda item: (item["device"], item["left"], item["top"], item["width"], item["height"]))


# -.-.-.-
def topology_token(
    monitors: Sequence[Mapping[str, Any]],
    metadata_by_index: Mapping[int, Mapping[str, Any]] | None = None,
    *,
    system_metadata: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Stable token that changes when geometry, primary display or effective DPI changes."""
    metadata_by_index = metadata_by_index or {}
    mss_entries: list[dict[str, Any]] = []
    for index, monitor in enumerate(monitors):
        if index == 0:
            continue
        left, top, width, height = _rect_tuple(monitor)
        meta = metadata_by_index.get(index, {})
        mss_entries.append(
            {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "device": str(meta.get("device") or ""),
                "primary": bool(meta.get("primary", False)),
                "dpi_x": int(meta.get("dpi_x") or _DEFAULT_DPI),
                "dpi_y": int(meta.get("dpi_y") or _DEFAULT_DPI),
            }
        )
    payload = {
        "mss": mss_entries,
        "system": _metadata_signature(system_metadata or []),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


# -.-.-.-
def display_topology_state(
    monitors: Sequence[Mapping[str, Any]],
) -> tuple[dict[int, dict[str, Any]], str]:
    raw_metadata = windows_monitor_metadata()
    matched = match_monitor_metadata(monitors, raw_metadata)
    return matched, topology_token(monitors, matched, system_metadata=raw_metadata)


# -.-.-.-
def monitor_metadata_by_index(monitors: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    metadata, _token = display_topology_state(monitors)
    return metadata


# -.-.-.-
def current_topology_token() -> str:
    try:
        import mss

        with per_monitor_dpi_context():
            with mss.mss() as sct:
                monitors = list(sct.monitors)
        _metadata, token = display_topology_state(monitors)
        return token
    except Exception:
        return ""


# -.-.-.-
def describe_dpi_metadata(
    monitor_index: int,
    metadata_by_index: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    meta = metadata_by_index.get(int(monitor_index), {})
    dpi_x = int(meta.get("dpi_x") or _DEFAULT_DPI)
    dpi_y = int(meta.get("dpi_y") or _DEFAULT_DPI)
    return {
        "device": str(meta.get("device") or ""),
        "primary": bool(meta.get("primary", False)),
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "scale_x": float(meta.get("scale_x") or (dpi_x / _DEFAULT_DPI)),
        "scale_y": float(meta.get("scale_y") or (dpi_y / _DEFAULT_DPI)),
    }
