from __future__ import annotations

import json

from core.computer_use import get_realtime_computer_use_session


PLUGIN = {
    "name": "realtime_computer_use",
    "description": (
        "Use ONLY for multi-step visual desktop tasks that cannot be completed with "
        "cheaper structured tools such as open_app, browser_control, windows_ui_automation, "
        "computer_settings, computer_control, file_controller or file_processor. It keeps a "
        "local live desktop capture, detects meaningful frame changes, rejects stale visual "
        "plans, and calls vision only when needed. Use display_manager first when the user "
        "explicitly identifies monitor/screen 1/2/3. Actions: start, status, pause, resume, "
        "stop. Approval is intentionally unavailable through this model-callable tool and "
        "must come from the trusted local approval surface. Never use this for a single "
        "click, scroll, typing command, browser DOM task, file operation, or app launch."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "start | status | pause | resume | stop",
            },
            "objective": {
                "type": "STRING",
                "description": "Complete visual objective for start.",
            },
            "target_window": {
                "type": "STRING",
                "description": (
                    "Optional local window title fragment to keep as the explicit visual target."
                ),
            },
            "monitor": {
                "type": "STRING",
                "description": (
                    "Optional display target: active | all | 1 | 2 | 3 or 'monitor 2'. "
                    "Omit to follow the foreground window automatically."
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
                monitor=(parameters or {}).get("monitor"),
                cost_mode=(parameters or {}).get("cost_mode", ""),
                max_steps=(parameters or {}).get("max_steps"),
                player=player,
            )
        elif action == "status":
            result = {"ok": True, "status": session.status()}
        elif action == "pause":
            result = session.pause()
        elif action == "resume":
            result = session.resume()
        elif action == "stop":
            result = session.stop()
        elif action == "approve":
            result = {
                "ok": False,
                "error": (
                    "Computer Use approval cannot be granted through the model-callable tool. "
                    "Use the trusted local approval surface."
                ),
            }
        else:
            result = {
                "ok": False,
                "error": "Use action=start, status, pause, resume or stop.",
            }
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}

    return json.dumps(result, ensure_ascii=False)
