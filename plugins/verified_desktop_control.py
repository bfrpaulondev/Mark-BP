from __future__ import annotations

from actions.real_browser_cdp import real_browser_cdp
from actions.real_browser_control import real_browser_control
from actions.verified_desktop_control import verified_desktop_control


_BROWSER_ACTIONS = {
    "browser_list_windows",
    "browser_focus_window",
    "browser_list_tabs",
    "browser_next_tab",
    "browser_previous_tab",
    "browser_switch_tab",
    "browser_switch_tab_url",
    "browser_current",
}

_CDP_ACTIONS = {
    "browser_cdp_status",
    "browser_cdp_list_tabs",
    "browser_cdp_switch_tab",
}


PLUGIN = {
    "name": "verified_desktop_control",
    "description": (
        "Verified zero/low-token control for the user's real Windows desktop. Use this for already-open "
        "real browser windows/tabs and for mouse movement that must be confirmed. It can list/focus browser "
        "windows, list tabs, switch tabs by index/title/URL, inspect the current tab and move the cursor with "
        "explicit verification. If the user's Chromium browser was already explicitly started with local remote "
        "debugging, browser_cdp_status/browser_cdp_list_tabs/browser_cdp_switch_tab may use that exact loopback "
        "endpoint as a structured fallback when UI Automation cannot expose the tab state. Antonella never scans "
        "ports, enables remote debugging, or relaunches the browser for CDP. Every effect result exposes a verified "
        "boolean. Do not create a separate Playwright browser session just to navigate the user's existing browser. "
        "If verified=false, never tell the user the action succeeded."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "browser_list_windows | browser_focus_window | browser_list_tabs | browser_next_tab | "
                    "browser_previous_tab | browser_switch_tab | browser_switch_tab_url | browser_current | "
                    "browser_cdp_status | browser_cdp_list_tabs | browser_cdp_switch_tab | "
                    "cursor_position | mouse_move | mouse_move_relative | mouse_wiggle"
                ),
            },
            "browser": {
                "type": "STRING",
                "description": "Optional browser: chrome | edge | firefox | opera | brave | vivaldi.",
            },
            "window": {
                "type": "STRING",
                "description": (
                    "Optional real browser-window selector: 1-based window index from browser_list_windows "
                    "or a unique visible window-title fragment."
                ),
            },
            "tab": {
                "type": "STRING",
                "description": (
                    "For browser_switch_tab/browser_cdp_switch_tab: a 1-based tab index or unique tab-title fragment."
                ),
            },
            "url": {
                "type": "STRING",
                "description": "URL or URL fragment used to identify a browser tab when supported by the action.",
            },
            "cdp_port": {
                "type": "INTEGER",
                "description": (
                    "Explicit loopback Chromium DevTools port for browser_cdp_* actions; default 9222. "
                    "Antonella never scans for an alternative port."
                ),
            },
            "x": {"type": "INTEGER", "description": "Absolute virtual-desktop X coordinate."},
            "y": {"type": "INTEGER", "description": "Absolute virtual-desktop Y coordinate."},
            "dx": {"type": "INTEGER", "description": "Relative horizontal mouse movement."},
            "dy": {"type": "INTEGER", "description": "Relative vertical mouse movement."},
        },
        "required": ["action"],
    },
}


# -.-.-.-
def is_available() -> bool:
    try:
        import platform

        return platform.system() == "Windows"
    except Exception:
        return False


# -.-.-.-
def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "").strip().lower()
    if action in _CDP_ACTIONS:
        return real_browser_cdp(
            parameters=params,
            player=player,
            session_memory=session_memory,
        )
    if action in _BROWSER_ACTIONS:
        return real_browser_control(
            parameters=params,
            player=player,
            session_memory=session_memory,
        )
    return verified_desktop_control(
        parameters=params,
        player=player,
        session_memory=session_memory,
    )
