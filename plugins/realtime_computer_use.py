from __future__ import annotations

import json

from core.computer_use import get_realtime_computer_use_session


PLUGIN = {
    "name": "realtime_computer_use",
    "description": (
        "Use ONLY for multi-step visual desktop tasks that cannot be completed with "
        "cheaper structured tools such as open_app, browser_control, computer_settings, "
        "computer_control, file_controller or file_processor. It keeps a local live "
        "desktop capture, detects meaningful frame changes, and calls vision only when "
        "needed. Good for remote desktops such as ScreenConnect or unknown desktop UIs. "
        "Actions: start, status, stop, approve. Never use this for a single click, scroll, "
        "typing command, browser DOM task, file operation, or app launch."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "start | status | stop | approve",
            },
            "objective": {
                "type": "STRING",
                "description": "Complete visual objective for start.",
            },
            "target_window": {
                "type": "STRING",
                "description": (
                    "Optional local window title fragment to focus first, e.g. ScreenConnect."
                ),
            },
            "cost_mode": {
                "type": "STRING",
                "description": "economy | balanced | quality. Default: economy.",
            },
            "max_steps": {
                "type": "INTEGER",
                "description": "Optional lower step cap. Cannot exceed the mode budget.",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    session = get_realtime_computer_use_session()
    action = str((parameters or {}).get("action") or "").strip().lower()

    try:
        if action == "start":
            result = session.start(
                objective=(parameters or {}).get("objective", ""),
                target_window=(parameters or {}).get("target_window", ""),
                cost_mode=(parameters or {}).get("cost_mode", ""),
                max_steps=(parameters or {}).get("max_steps"),
                player=player,
            )
        elif action == "status":
            result = {"ok": True, "status": session.status()}
        elif action == "stop":
            result = session.stop()
        elif action == "approve":
            result = session.approve_once()
        else:
            result = {
                "ok": False,
                "error": "Use action=start, status, stop or approve.",
            }
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}

    return json.dumps(result, ensure_ascii=False)
