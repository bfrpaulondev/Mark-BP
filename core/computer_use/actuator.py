from __future__ import annotations

import time

from core.computer_use.contracts import ComputerAction, FrameSnapshot


_VISUAL_ACTIONS = {
    "click",
    "double_click",
    "right_click",
    "scroll",
    "type",
    "smart_type",
    "hotkey",
    "press",
    "move",
}


def execute_action(
    action: ComputerAction,
    frame: FrameSnapshot,
    *,
    player=None,
) -> tuple[str, bool]:
    if action.action == "wait":
        time.sleep(action.seconds)
        return f"Waited {action.seconds:.1f}s", False

    if action.action in {"done", "fail"}:
        return action.result or action.description or action.action, False

    from actions.computer_control import computer_control

    params: dict = {"action": action.action}

    if action.action in {"click", "double_click", "right_click", "move"}:
        if action.x is None or action.y is None:
            return f"{action.action} requires x and y coordinates.", False
        screen_x, screen_y = frame.to_screen_coordinates(action.x, action.y)
        params.update({"x": screen_x, "y": screen_y})

    elif action.action == "scroll":
        params.update(
            {
                "direction": action.direction or "down",
                "amount": action.amount,
            }
        )

    elif action.action in {"type", "smart_type"}:
        params["text"] = action.text
        if action.action == "smart_type":
            params["clear_first"] = False

    elif action.action == "hotkey":
        params["keys"] = action.keys

    elif action.action == "press":
        params["key"] = action.key or "enter"

    else:
        return f"Unsupported Computer Use action: {action.action}", False

    result = computer_control(parameters=params, player=player)
    return str(result or "Done."), action.action in _VISUAL_ACTIONS
