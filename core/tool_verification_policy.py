from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_ALWAYS_VERIFY = {
    "open_app",
    "computer_control",
    "computer_settings",
    "verified_desktop_control",
    "verified_browser_automation",
    "send_message",
    "reminder",
}

_UIA_EFFECT_ACTIONS = {
    "click",
    "set_text",
}

_BROWSER_EFFECT_ACTIONS = {
    "go_to",
    "search",
    "click",
    "type",
    "scroll",
    "fill_form",
    "smart_click",
    "smart_type",
    "press",
    "new_tab",
    "close_tab",
    "back",
    "forward",
    "reload",
    "switch",
    "close",
    "close_all",
}

_FILE_EFFECT_ACTIONS = {
    "create_file",
    "create_folder",
    "delete",
    "move",
    "copy",
    "rename",
    "write",
    "organize_desktop",
}

_DESKTOP_EFFECT_ACTIONS = {
    "wallpaper",
    "wallpaper_url",
    "organize",
    "clean",
    "task",
}

_GAME_EFFECT_ACTIONS = {
    "update",
    "install",
    "schedule",
    "cancel_schedule",
}

_CODE_EFFECT_ACTIONS = {
    "write",
    "edit",
    "run",
    "build",
    "auto",
}


# -.-.-.-
def requires_postcondition(tool_name: str, args: Mapping[str, Any] | None = None) -> bool:
    """Return whether a tool result must carry explicit evidence before success may be claimed."""
    name = str(tool_name or "").strip().lower()
    params = args or {}
    action = str(params.get("action") or "").strip().lower()

    if name in _ALWAYS_VERIFY:
        return True
    if name == "windows_ui_automation":
        return action in _UIA_EFFECT_ACTIONS
    if name == "browser_control":
        return action in _BROWSER_EFFECT_ACTIONS
    if name == "file_controller":
        return action in _FILE_EFFECT_ACTIONS
    if name == "desktop_control":
        return action in _DESKTOP_EFFECT_ACTIONS
    if name == "game_updater":
        return action in _GAME_EFFECT_ACTIONS
    if name == "code_helper":
        return action in _CODE_EFFECT_ACTIONS
    if name == "dev_agent":
        return True
    if name == "shutdown_jarvis":
        return True
    return False
