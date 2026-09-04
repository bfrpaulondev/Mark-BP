from __future__ import annotations

from actions.verified_desktop_control import verified_desktop_control


PLUGIN = {
    "name": "verified_desktop_control",
    "description": (
        "Verified zero/low-token control for the user's real Windows desktop. Use this for browser tab "
        "navigation in an already-open real browser and for mouse movement that must be confirmed. "
        "Unlike legacy tab/mouse commands, this tool returns an explicit verified boolean. For browser "
        "tabs use browser_list_tabs, browser_next_tab, browser_previous_tab or browser_switch_tab. "
        "For mouse requests use cursor_position, mouse_move, mouse_move_relative or mouse_wiggle. "
        "If verified=false, never tell the user the action succeeded."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "browser_list_tabs | browser_next_tab | browser_previous_tab | browser_switch_tab | "
                    "cursor_position | mouse_move | mouse_move_relative | mouse_wiggle"
                ),
            },
            "browser": {
                "type": "STRING",
                "description": "Optional browser: chrome | edge | firefox | opera | brave | vivaldi.",
            },
            "tab": {
                "type": "STRING",
                "description": "For browser_switch_tab: tab number 1-9 or a visible tab-title fragment.",
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
    return verified_desktop_control(
        parameters=parameters,
        player=player,
        session_memory=session_memory,
    )
