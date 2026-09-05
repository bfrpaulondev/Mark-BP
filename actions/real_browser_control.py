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
    for browser_name, process_names in _BROWSER_PROCESS_ALIASES.items():
        if process in process_names:
            return browser_name
    return ""


# -.-.-.-
def _window_title(hwnd: int) -> str:
    if platform.system() != "Windows" or not hwnd:
        return ""
    try:
        user32 = ctypes.windll.user32
        length = int(user32.GetWindowTextLengthW(hwnd) or 0)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return str(buffer.value or "").strip()
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
            process_name = str(psutil.Process(int(pid.value)).name() or "").lower()
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
def _browser_windows() -> list[dict[str, Any]]:
    if platform.system() != "Windows":
        return []
    try:
        import psutil

        user32 = ctypes.windll.user32
        allowed_processes = {
            process
            for process_names in _BROWSER_PROCESS_ALIASES.values()
            for process in process_names
        }
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
                process_name = str(psutil.Process(int(pid.value)).name() or "").lower()
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
                        "title": title[:240],
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
def _select_window(
    candidates: list[dict[str, Any]],
    browser_name: str = "",
    window_selector: Any = None,
    foreground_hwnd: int = 0,
) -> tuple[dict[str, Any] | None, str]:
    requested_browser = _normalize_browser_name(browser_name)
    filtered = [
        item
        for item in candidates
        if not requested_browser or item.get("browser") == requested_browser
    ]
    if not filtered:
        target = requested_browser or "browser"
        return None, f"No visible {target} browser window was found."

    selector = str(window_selector or "").strip()
    if selector:
        if selector.isdigit():
            index = int(selector)
            if index < 1 or index > len(filtered):
                return None, f"Browser window index {index} is out of range (1-{len(filtered)})."
            return filtered[index - 1], "index"
        needle = selector.casefold()
        matches = [item for item in filtered if needle in str(item.get("title") or "").casefold()]
        if len(matches) == 1:
            return matches[0], "title"
        if not matches:
            return None, f"No browser window title matched '{selector}'."
        return None, f"More than one browser window title matched '{selector}'; use a window index."

    for item in filtered:
        if int(item.get("hwnd") or 0) == int(foreground_hwnd or 0):
            return item, "foreground"

    distinct_browsers = {str(item.get("browser") or "") for item in filtered}
    if not requested_browser and len(distinct_browsers) > 1:
        return None, "Multiple browser applications are visible; specify a browser or window."
    if len(filtered) > 1:
        return None, "Multiple browser windows match; specify a window index or title fragment."
    return filtered[0], "single"


# -.-.-.-
def _focus_window(target: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if platform.system() != "Windows":
        return False, {}
    hwnd = int(target.get("hwnd") or 0)
    if not hwnd:
        return False, {}
    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.18)
    except Exception:
        return False, _foreground_window()
    after = _foreground_window()
    return int(after.get("hwnd") or 0) == hwnd, after


# -.-.-.-
def _resolve_and_focus(
    browser_name: str = "",
    window_selector: Any = None,
) -> tuple[dict[str, Any] | None, str]:
    if platform.system() != "Windows":
        return None, "Verified real-browser control currently requires Windows."
    foreground = _foreground_window()
    candidates = _browser_windows()
    target, reason = _select_window(
        candidates,
        browser_name,
        window_selector,
        int(foreground.get("hwnd") or 0),
    )
    if target is None:
        return None, reason
    if int(foreground.get("hwnd") or 0) == int(target.get("hwnd") or 0):
        return target, reason
    focused, after = _focus_window(target)
    if not focused:
        return None, "The browser window was found, but Windows did not allow it to become foreground."
    resolved = dict(target)
    resolved.update({"title": str(after.get("title") or target.get("title") or "")})
    return resolved, "focused"


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
            selected = False
            try:
                selected = bool(control.is_selected())
            except Exception:
                try:
                    selected = bool(control.has_keyboard_focus())
                except Exception:
                    pass
            result.append(
                {
                    "index": index,
                    "name": name[:240],
                    "selected": selected,
                    "control": control,
                }
            )
        return result
    except Exception:
        return []


# -.-.-.-
def _public_tabs(tabs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": int(item["index"]),
            "name": str(item["name"]),
            "selected": bool(item.get("selected")),
        }
        for item in tabs
    ]


# -.-.-.-
def _selected_tab(tabs: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((item for item in tabs if item.get("selected")), None)


# -.-.-.-
def _select_tab(tabs: list[dict[str, Any]], selector: Any) -> tuple[dict[str, Any] | None, str]:
    raw = str(selector or "").strip()
    if not raw:
        return None, "Specify a tab index or title."
    if raw.isdigit():
        index = int(raw)
        match = next((item for item in tabs if int(item.get("index") or 0) == index), None)
        if match is None:
            return None, f"Browser tab index {index} is out of range."
        return match, "index"
    needle = raw.casefold()
    matches = [item for item in tabs if needle in str(item.get("name") or "").casefold()]
    if len(matches) == 1:
        return matches[0], "title"
    if not matches:
        return None, f"No visible browser tab matched '{raw}'."
    return None, f"More than one browser tab matched '{raw}'; use a tab index."


# -.-.-.-
def _read_browser_url() -> str:
    try:
        import pyautogui
        import pyperclip

        previous_clipboard = pyperclip.paste()
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "c")
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
def _fingerprint(hwnd: int) -> dict[str, Any]:
    tabs = _uia_tabs(hwnd)
    selected = _selected_tab(tabs)
    return {
        "title": _window_title(hwnd),
        "url": _read_browser_url(),
        "selected_tab": (
            {"index": selected.get("index"), "name": selected.get("name")}
            if selected
            else None
        ),
    }


# -.-.-.-
def _fingerprint_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return bool(
        (before.get("url") and after.get("url") and before.get("url") != after.get("url"))
        or (before.get("title") and after.get("title") and before.get("title") != after.get("title"))
        or (before.get("selected_tab") != after.get("selected_tab"))
    )


# -.-.-.-
def _url_matches(actual: str, requested: str) -> bool:
    actual_value = str(actual or "").strip().casefold()
    requested_value = str(requested or "").strip().casefold()
    return bool(actual_value and requested_value and requested_value in actual_value)


# -.-.-.-
def _list_windows() -> str:
    foreground = _foreground_window()
    windows = _browser_windows()
    payload = []
    for index, item in enumerate(windows, start=1):
        payload.append(
            {
                "index": index,
                "browser": item.get("browser"),
                "process": item.get("process"),
                "title": item.get("title"),
                "active": int(item.get("hwnd") or 0) == int(foreground.get("hwnd") or 0),
            }
        )
    return _json(
        {
            "ok": bool(payload),
            "delivered": True,
            "verified": True,
            "action": "browser_list_windows",
            "windows": payload,
            "message": f"Found {len(payload)} visible browser window(s).",
        }
    )


# -.-.-.-
def _focus_browser_window(browser: str, window: Any) -> str:
    target, reason = _resolve_and_focus(browser, window)
    if target is None:
        return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_focus_window", "error": reason})
    foreground = _foreground_window()
    verified = int(foreground.get("hwnd") or 0) == int(target.get("hwnd") or 0)
    return _json(
        {
            "ok": verified,
            "delivered": True,
            "verified": verified,
            "action": "browser_focus_window",
            "browser": target.get("browser"),
            "title": target.get("title"),
            "message": "Browser window focus verified." if verified else "Browser window focus could not be verified.",
        }
    )


# -.-.-.-
def _list_tabs(browser: str, window: Any) -> str:
    target, reason = _resolve_and_focus(browser, window)
    if target is None:
        return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_list_tabs", "error": reason})
    tabs = _uia_tabs(int(target["hwnd"]))
    if not tabs:
        return _json(
            {
                "ok": False,
                "delivered": True,
                "verified": False,
                "action": "browser_list_tabs",
                "browser": target.get("browser"),
                "error": "The browser window is focused, but its tab strip is not exposed through Windows UI Automation.",
            }
        )
    return _json(
        {
            "ok": True,
            "delivered": True,
            "verified": True,
            "action": "browser_list_tabs",
            "browser": target.get("browser"),
            "window_title": target.get("title"),
            "tabs": _public_tabs(tabs),
        }
    )


# -.-.-.-
def _switch_relative(direction: str, browser: str, window: Any) -> str:
    try:
        import pyautogui
    except ImportError:
        return _json({"ok": False, "delivered": False, "verified": False, "action": f"browser_{direction}_tab", "error": "pyautogui is unavailable."})
    target, reason = _resolve_and_focus(browser, window)
    if target is None:
        return _json({"ok": False, "delivered": False, "verified": False, "action": f"browser_{direction}_tab", "error": reason})
    hwnd = int(target["hwnd"])
    before = _fingerprint(hwnd)
    if direction == "next":
        pyautogui.hotkey("ctrl", "tab")
    else:
        pyautogui.hotkey("ctrl", "shift", "tab")
    time.sleep(0.22)
    after = _fingerprint(hwnd)
    verified = _fingerprint_changed(before, after)
    return _json(
        {
            "ok": verified,
            "delivered": True,
            "verified": verified,
            "action": f"browser_{direction}_tab",
            "browser": target.get("browser"),
            "before": before,
            "after": after,
            "message": "Browser tab change verified." if verified else "The tab shortcut was delivered, but the active tab did not produce a verifiable change.",
        }
    )


# -.-.-.-
def _activate_tab_control(target: dict[str, Any], tab_item: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    hwnd = int(target["hwnd"])
    before = _fingerprint(hwnd)
    if tab_item.get("selected"):
        return True, {"before": before, "after": before, "already_active": True}
    try:
        tab_item["control"].click_input()
        time.sleep(0.22)
    except Exception:
        return False, {"before": before, "after": before, "already_active": False}
    after = _fingerprint(hwnd)
    selected = after.get("selected_tab") or {}
    expected_index = int(tab_item.get("index") or 0)
    expected_name = str(tab_item.get("name") or "")
    verified = bool(
        int(selected.get("index") or 0) == expected_index
        or (expected_name and expected_name.casefold() in str(after.get("title") or "").casefold())
    )
    return verified, {"before": before, "after": after, "already_active": False}


# -.-.-.-
def _switch_tab(browser: str, window: Any, tab: Any) -> str:
    target, reason = _resolve_and_focus(browser, window)
    if target is None:
        return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_switch_tab", "error": reason})
    tabs = _uia_tabs(int(target["hwnd"]))
    if tabs:
        tab_item, select_reason = _select_tab(tabs, tab)
        if tab_item is None:
            return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_switch_tab", "browser": target.get("browser"), "error": select_reason})
        verified, transition = _activate_tab_control(target, tab_item)
        return _json(
            {
                "ok": verified,
                "delivered": True,
                "verified": verified,
                "action": "browser_switch_tab",
                "browser": target.get("browser"),
                "tab": {"index": tab_item.get("index"), "name": tab_item.get("name")},
                "transition": transition,
                "message": "Requested browser tab is active and verified." if verified else "The tab control was activated, but the resulting active tab could not be verified.",
            }
        )

    raw_tab = str(tab or "").strip()
    if not raw_tab.isdigit() or not 1 <= int(raw_tab) <= 9:
        return _json(
            {
                "ok": False,
                "delivered": False,
                "verified": False,
                "action": "browser_switch_tab",
                "browser": target.get("browser"),
                "error": "Tab UI Automation is unavailable; only numeric tabs 1-9 can use the keyboard fallback.",
            }
        )
    try:
        import pyautogui

        before = _fingerprint(int(target["hwnd"]))
        pyautogui.hotkey("ctrl", raw_tab)
        time.sleep(0.22)
        after = _fingerprint(int(target["hwnd"]))
        verified = _fingerprint_changed(before, after)
        return _json(
            {
                "ok": verified,
                "delivered": True,
                "verified": verified,
                "action": "browser_switch_tab",
                "browser": target.get("browser"),
                "tab": int(raw_tab),
                "before": before,
                "after": after,
                "message": "Browser tab switch verified." if verified else "Keyboard tab switch was delivered, but no resulting tab change was verified.",
            }
        )
    except Exception as exc:
        return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_switch_tab", "error": str(exc)})


# -.-.-.-
def _switch_tab_by_url(browser: str, window: Any, url_fragment: str) -> str:
    target, reason = _resolve_and_focus(browser, window)
    if target is None:
        return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_switch_tab_url", "error": reason})
    requested = str(url_fragment or "").strip()
    if not requested:
        return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_switch_tab_url", "error": "Specify a URL or URL fragment."})
    tabs = _uia_tabs(int(target["hwnd"]))
    if not tabs:
        return _json(
            {
                "ok": False,
                "delivered": False,
                "verified": False,
                "action": "browser_switch_tab_url",
                "browser": target.get("browser"),
                "error": "URL-based tab selection requires the browser tab strip to be exposed through Windows UI Automation.",
            }
        )
    original = _selected_tab(tabs)
    for tab_item in tabs[:40]:
        try:
            if not tab_item.get("selected"):
                tab_item["control"].click_input()
                time.sleep(0.16)
            actual_url = _read_browser_url()
            if _url_matches(actual_url, requested):
                after_tabs = _uia_tabs(int(target["hwnd"]))
                selected = _selected_tab(after_tabs)
                verified = bool(selected and int(selected.get("index") or 0) == int(tab_item.get("index") or 0) and _url_matches(actual_url, requested))
                return _json(
                    {
                        "ok": verified,
                        "delivered": True,
                        "verified": verified,
                        "action": "browser_switch_tab_url",
                        "browser": target.get("browser"),
                        "tab": {"index": tab_item.get("index"), "name": tab_item.get("name")},
                        "url": actual_url,
                        "message": "Browser tab URL match verified." if verified else "A URL match was observed, but the selected tab identity was not verified.",
                    }
                )
        except Exception:
            continue

    if original is not None:
        try:
            original["control"].click_input()
            time.sleep(0.12)
        except Exception:
            pass
    return _json(
        {
            "ok": False,
            "delivered": True,
            "verified": False,
            "action": "browser_switch_tab_url",
            "browser": target.get("browser"),
            "error": f"No visible tab URL matched '{requested}'. The original tab was restored when possible.",
        }
    )


# -.-.-.-
def _current(browser: str, window: Any) -> str:
    target, reason = _resolve_and_focus(browser, window)
    if target is None:
        return _json({"ok": False, "delivered": False, "verified": False, "action": "browser_current", "error": reason})
    fingerprint = _fingerprint(int(target["hwnd"]))
    return _json(
        {
            "ok": True,
            "delivered": True,
            "verified": True,
            "action": "browser_current",
            "browser": target.get("browser"),
            "window_title": target.get("title"),
            "current": fingerprint,
        }
    )


# -.-.-.-
def real_browser_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    browser = _normalize_browser_name(params.get("browser"))
    window = params.get("window")

    if player:
        try:
            player.write_log(f"SYS: Real browser · {action or 'missing action'}")
        except Exception:
            pass

    if action == "browser_list_windows":
        return _list_windows()
    if action == "browser_focus_window":
        return _focus_browser_window(browser, window)
    if action == "browser_list_tabs":
        return _list_tabs(browser, window)
    if action == "browser_next_tab":
        return _switch_relative("next", browser, window)
    if action == "browser_previous_tab":
        return _switch_relative("previous", browser, window)
    if action == "browser_switch_tab":
        return _switch_tab(browser, window, params.get("tab"))
    if action == "browser_switch_tab_url":
        return _switch_tab_by_url(browser, window, str(params.get("url") or ""))
    if action == "browser_current":
        return _current(browser, window)

    return _json(
        {
            "ok": False,
            "delivered": False,
            "verified": False,
            "action": action,
            "error": "Unsupported real browser action.",
        }
    )
