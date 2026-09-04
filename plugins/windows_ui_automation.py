from __future__ import annotations

from actions.windows_ui_automation import windows_ui_automation


PLUGIN = {
    "name": "windows_ui_automation",
    "description": (
        "Zero-token structured Windows UI Automation. Use this BEFORE screen vision or "
        "realtime_computer_use when interacting with a normal Windows application. It can "
        "list top-level windows, inspect accessible controls, find a control by visible name, "
        "automation_id or control_type, click/invoke it, and set text in edit controls. "
        "This often works for native/desktop apps without sending screenshots to any model. "
        "If a remote desktop such as ScreenConnect exposes only one graphical surface and no "
        "useful child controls, then fall back to realtime_computer_use."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "list_windows | inspect | find | click | set_text",
            },
            "window": {
                "type": "STRING",
                "description": "Optional window title fragment. Omit to use the foreground window.",
            },
            "name": {
                "type": "STRING",
                "description": "Visible control name/text to match.",
            },
            "automation_id": {
                "type": "STRING",
                "description": "Stable Windows UI Automation identifier when known.",
            },
            "control_type": {
                "type": "STRING",
                "description": "Optional UIA type such as Button, Edit, TabItem, ListItem or MenuItem.",
            },
            "text": {
                "type": "STRING",
                "description": "Text for set_text.",
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Clear an edit control before set_text. Default true.",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum controls/windows returned by inspect/list_windows. Default 80.",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    return windows_ui_automation(
        parameters=parameters,
        player=player,
        session_memory=session_memory,
    )
