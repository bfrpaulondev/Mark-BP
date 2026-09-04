from __future__ import annotations

import ctypes
import json
import platform
import time
from ctypes import wintypes
from typing import Any


_BROWSER_PROCESS_ALIASES = {
    "chrome": {"chrome.exe"},
    "edge": {"msedge.exe"},
    "firefox": {"firefox.exe"},
    "opera": {"opera.exe"},
    "operagx": {"opera.exe"},
    "brave": {"brave.exe"},
    "vivaldi": {"vivaldi.exe"},
}

_BROWSER_NAME_ALIASES = {
    "google chrome": "chrome",
    "google-chrome": "chrome",
    "microsoft edge": "edge",
    "ms edge": "edge",
    "msedge": "edge",
    "mozilla firefox": "firefox",
    "opera gx": "operagx",
    "opera_gx": "operagx",
}


# -.-.-.-
def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


# -.-.-.-
def _normalize_browser_name(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return _BROWSER_NAME_ALIASES.get(raw, raw)


# -.-.-.-
def _browser_name_from_process(process_name: str) -> str:
    process = str(process_name or "").strip().lower()
    for browser_name, processes in _BROWSER_PROCESS_ALIASES.items():
        if process in processes:
            return browser_name
    return ""


# -.-.-.-
def _window_title(hwnd: int) -> str:
    if platform.system() != "Windows" or not hwnd:
        return ""
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()
    except Exception:
        return ""


# -.-.-.-
def _foreground_window() -> dict[str, Any]:
    if platform.system() != "Windows":
        return {}

    try:
        import psutil

        user32 = ctypes.windll.user32
        hwnd = int(user32.GetForegroundWindow() or 0)
        if not hwnd:
            return {}
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = ""
        try:
            process_name = psutil.Process(int(pid.value)).name().lower()
        except Exception:
            pass
        return {
            "hwnd": hwnd,
            "pid": int(pid.value),
            "process": process_name,
            "browser": _browser_name_from_process(process_name),
            "title": _window_title(hwnd),
        }
    except Exception:
        return {}


# -.-.-.-
def _browser_windows(browser_name: str = "") -> list[dict[str, Any]]:
    if platform.system() != "Windows":
        return []

    try:
        import psutil

        user32 = ctypes.windll.user32
        requested = _normalize_browser_name(browser_name)
        allowed_processes: set[str] = set()
        if requested:
            allowed_processes = set(_BROWSER_PROCESS_ALIASES.get(requested, set()))
        else:
            for values in _BROWSER_PROCESS_ALIASES.values():
                allowed_processes.update(values)

        results: list[dict[str, Any]] = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _collect(hwnd, _lparam):
            try:
                if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                    return True
                title = _window_title(int(hwnd))
                if not title:
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process_name = psutil.Process(int(pid.value)).name().lower()
                if process_name not in allowed_processes:
                    return True
                rect = wintypes.RECT()
                area = 0
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    area = max(0, int(rect.right - rect.left)) * max(0, int(rect.bottom - rect.top))
                results.append(
                    {
                        "hwnd": int(hwnd),
                        "pid": int(pid.value),
                        "process": process_name,
                        "browser": _browser_name_from_process(process_name),
                        "title": title,
                        "area": area,
                    }
                )
            except Exception:
                pass
            return True

        user32.EnumWindows(callback_type(_collect), 0)
        return sorted(results, key=lambda item: int(item.get("area") or 0), reverse=True)
    except Exception:
        return []


# -.-.-.-
def _focus_browser(browser_name: str = "") -> tuple[dict[str, Any] | None, str]:
    if platform.system() != "Windows":
        return None, "Verified browser-tab control currently requires Windows."

    requested = _normalize_browser_name(browser_name)
    foreground = _foreground_window()
    if foreground.get("browser") and (not requested or foreground.get("browser") == requested):
        return foreground, "foreground"

    candidates = _browser_windows(requested)
    if not candidates:
        target = requested or "browser"
        return None, f"No visible {target} browser window was found."

    if not requested:
        distinct = {str(item.get("browser") or "") for item in candidates}
        if len(distinct) > 1:
            return None, "Multiple browser applications are visible; specify chrome, edge, firefox, opera, brave or vivaldi."

    target = candidates[0]
    hwnd = int(target["hwnd"])
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.18)
    except Exception as exc:
        return None, f"Could not focus browser window: {exc}"

    after = _foreground_window()
    if int(after.get("hwnd") or 0) != hwnd:
        return None, "Browser window was found but Windows did not allow it to become foreground."
    return after, "focused"


# -.-.-.-
def _read_browser_url() -> str:
    try:
        import pyautogui
        import pyperclip

        previous_clipboard = pyperclip.paste()
        modifier = "command" if platform.system() == "Darwin" else "ctrl"
        pyautogui.hotkey(modifier, "l")
        time.sleep(0.05)
        pyautogui.hotkey(modifier, "c")
        time.sleep(0.08)
        value = str(pyperclip.paste() or "").strip()
        pyautogui.press("esc")
        try:
            pyperclip.copy(previous_clipboard)
        except Exception:
            pass
        return value
    except Exception:
        return ""


# -.-.-.-
def _browser_fingerprint() -> dict[str, str]:
    current = _foreground_window()
    return {
        "title": str(current.get("title") or ""),
        "url": _read_browser_url(),
    }


# -.-.-.-
def _fingerprint_changed(before: dict[str, str], after: dict[str, str]) -> bool:
    before_title = str(before.get("title") or "").strip()
    after_title = str(after.get("title") or "").strip()
    before_url = str(before.get("url") or "").strip()
    after_url = str(after.get("url") or "").strip()
    return bool(
        (before_url and after_url and before_url != after_url)
        or (before_title and after_title and before_title != after_title)
    )


# -.-.-.-
def _uia_tabs(hwnd: int) -> list[dict[str, Any]]:
    try:
        from pywinauto import Desktop

        window = Desktop(backend="uia").window(handle=int(hwnd))
        controls = window.descendants(control_type="TabItem")
        result: list[dict[str, Any]] = []
        for index, control in enumerate(controls, start=1):
            try:
                name = str(control.window_text() or "").strip()
            except Exception:
                name = ""
            if not name:
                continue
            result.append({"index": index, "name": name, "control": control})
        return result
    except Exception:
        return []


# -.-.-.-
def _browser_list_tabs(browser_name: str = "") -> str:
    window, reason = _focus_browser(browser_name)
    if window is None:
        return _json({"ok": False, "verified": False, "action": "browser_list_tabs", "error": reason})

    tabs = _uia_tabs(int(window["hwnd"]))
    if not tabs:
        return _json(
            {
                "ok": False,
                "verified": False,
                "action": "browser_list_tabs",
                "browser": window.get("browser"),
                "error": "The browser is focused, but its tab strip is not exposed through Windows UI Automation.",
            }
        )

    return _json(
        {
            "ok": True,
            "verified": True,
            "action": "browser_list_tabs",
            "browser": window.get("browser"),
            "tabs": [{"index": item["index"], "name": item["name"]} for item in tabs],
        }
    )


# -.-.-.-
def _browser_switch_relative(direction: str, browser_name: str = "") -> str:
    try:
        import pyautogui
    except ImportError:
        return _json({"ok": False, "verified": False, "action": f"browser_{direction}_tab", "error": "pyautogui is not installed."})

    window, reason = _focus_browser(browser_name)
    if window is None:
        return _json({"ok": False, "verified": False, "action": f"browser_{direction}_tab", "error": reason})

    before = _browser_fingerprint()
    if direction == "next":
        pyautogui.hotkey("ctrl", "tab")
    else:
        pyautogui.hotkey("ctrl", "shift", "tab")
    time.sleep(0.22)
    after = _browser_fingerprint()
    verified = _fingerprint_changed(before, after)

    return _json(
        {
            "ok": verified,
            "verified": verified,
            "delivered": True,
            "action": f"browser_{direction}_tab",
            "browser": window.get("browser"),
            "before": before,
            "after": after,
            "message": (
                "Browser tab change verified."
                if verified
                else "The tab shortcut was delivered, but the active tab change could not be verified. Do not claim success."
            ),
        }
    )


# -.-.-.-
def _browser_switch_tab(tab: Any, browser_name: str = "") -> str:
    try:
        import pyautogui
    except ImportError:
        return _json({"ok": False, "verified": False, "action": "browser_switch_tab", "error": "pyautogui is not installed."})

    window, reason = _focus_browser(browser_name)
    if window is None:
        return _json({"ok": False, "verified": False, "action": "browser_switch_tab", "error": reason})

    before = _browser_fingerprint()
    raw_tab = str(tab or "").strip()
    if not raw_tab:
        return _json({"ok": False, "verified": False, "action": "browser_switch_tab", "error": "Specify a tab index or title."})

    if raw_tab.isdigit():
        index = max(1, min(9, int(raw_tab)))
        pyautogui.hotkey("ctrl", str(index))
        time.sleep(0.22)
        after = _browser_fingerprint()
        verified = _fingerprint_changed(before, after)
        return _json(
            {
                "ok": verified,
                "verified": verified,
                "delivered": True,
                "action": "browser_switch_tab",
                "browser": window.get("browser"),
                "tab": index,
                "before": before,
                "after": after,
                "message": (
                    f"Browser tab {index} verified."
                    if verified
                    else f"Ctrl+{index} was delivered, but the active tab change could not be verified. Do not claim success."
                ),
            }
        )

    needle = raw_tab.casefold()
    matches = [item for item in _uia_tabs(int(window["hwnd"])) if needle in item["name"].casefold()]
    if not matches:
        return _json(
            {
                "ok": False,
                "verified": False,
                "action": "browser_switch_tab",
                "browser": window.get("browser"),
                "error": f"No visible browser tab matched '{raw_tab}'.",
            }
        )

    try:
        matches[0]["control"].click_input()
        time.sleep(0.22)
    except Exception as exc:
        return _json(
            {
                "ok": False,
                "verified": False,
                "action": "browser_switch_tab",
                "browser": window.get("browser"),
                "error": f"The tab was found but could not be activated: {exc}",
            }
        )

    after = _browser_fingerprint()
    title_match = needle in str(after.get("title") or "").casefold()
    verified = _fingerprint_changed(before, after) or title_match
    return _json(
        {
            "ok": verified,
            "verified": verified,
            "delivered": True,
            "action": "browser_switch_tab",
            "browser": window.get("browser"),
            "tab": matches[0]["name"],
            "before": before,
            "after": after,
            "message": (
                f"Browser tab '{matches[0]['name']}' verified."
                if verified
                else "The tab control was activated, but the resulting active tab could not be verified. Do not claim success."
            ),
        }
    )


# -.-.-.-
def _virtual_desktop_bounds() -> tuple[int, int, int, int]:
    try:
        import mss

        with mss.mss() as sct:
            combined = sct.monitors[0]
            return (
                int(combined["left"]),
                int(combined["top"]),
                int(combined["left"] + combined["width"] - 1),
                int(combined["top"] + combined["height"] - 1),
            )
    except Exception:
        try:
            import pyautogui

            width, height = pyautogui.size()
            return 0, 0, int(width - 1), int(height - 1)
        except Exception:
            return 0, 0, 1919, 1079


# -.-.-.-
def _clamp_point(x: int, y: int, bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = bounds
    return min(max(int(x), left), right), min(max(int(y), top), bottom)


# -.-.-.-
def _cursor_position() -> tuple[int, int]:
    if platform.system() == "Windows":
        point = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return int(point.x), int(point.y)
    try:
        import pyautogui

        point = pyautogui.position()
        return int(point.x), int(point.y)
    except Exception:
        return 0, 0


# -.-.-.-
def _set_cursor_position(x: int, y: int) -> bool:
    if platform.system() == "Windows":
        return bool(ctypes.windll.user32.SetCursorPos(int(x), int(y)))
    try:
        import pyautogui

        pyautogui.moveTo(int(x), int(y), duration=0.2)
        return True
    except Exception:
        return False


# -.-.-.-
def _verified_mouse_move(x: int, y: int) -> str:
    target = _clamp_point(int(x), int(y), _virtual_desktop_bounds())
    before = _cursor_position()
    delivered = _set_cursor_position(*target)
    time.sleep(0.06)
    after = _cursor_position()
    verified = delivered and abs(after[0] - target[0]) <= 2 and abs(after[1] - target[1]) <= 2
    return _json(
        {
            "ok": verified,
            "verified": verified,
            "delivered": delivered,
            "action": "mouse_move",
            "before": {"x": before[0], "y": before[1]},
            "target": {"x": target[0], "y": target[1]},
            "after": {"x": after[0], "y": after[1]},
            "message": "Mouse movement verified." if verified else "Mouse movement could not be verified. Do not claim success.",
        }
    )


# -.-.-.-
def _verified_mouse_move_relative(dx: int, dy: int) -> str:
    current = _cursor_position()
    target = _clamp_point(current[0] + int(dx), current[1] + int(dy), _virtual_desktop_bounds())
    return _verified_mouse_move(*target)


# -.-.-.-
def verified_desktop_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    browser = _normalize_browser_name(params.get("browser"))

    if player:
        try:
            player.write_log(f"SYS: Verified control · {action or 'missing action'}")
        except Exception:
            pass

    if action == "browser_list_tabs":
        return _browser_list_tabs(browser)
    if action == "browser_next_tab":
        return _browser_switch_relative("next", browser)
    if action == "browser_previous_tab":
        return _browser_switch_relative("previous", browser)
    if action == "browser_switch_tab":
        return _browser_switch_tab(params.get("tab"), browser)
    if action == "cursor_position":
        x, y = _cursor_position()
        return _json({"ok": True, "verified": True, "action": "cursor_position", "x": x, "y": y})
    if action == "mouse_move":
        if params.get("x") is None or params.get("y") is None:
            return _json({"ok": False, "verified": False, "action": "mouse_move", "error": "mouse_move requires x and y."})
        return _verified_mouse_move(int(params["x"]), int(params["y"]))
    if action == "mouse_move_relative":
        return _verified_mouse_move_relative(int(params.get("dx") or 0), int(params.get("dy") or 0))
    if action == "mouse_wiggle":
        dx = int(params.get("dx") or 120)
        dy = int(params.get("dy") or 60)
        if dx == 0 and dy == 0:
            dx = 120
        return _verified_mouse_move_relative(dx, dy)

    return _json(
        {
            "ok": False,
            "verified": False,
            "action": action,
            "error": (
                "Use browser_list_tabs, browser_next_tab, browser_previous_tab, browser_switch_tab, "
                "cursor_position, mouse_move, mouse_move_relative or mouse_wiggle."
            ),
        }
    )
