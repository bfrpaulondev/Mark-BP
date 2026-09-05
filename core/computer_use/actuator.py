from __future__ import annotations

import time

from core.computer_use.contracts import ComputerAction, FrameSnapshot
from core.display_topology import current_topology_token, per_monitor_dpi_context


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

_CHANGE_EXPECTED_ACTIONS = _VISUAL_ACTIONS - {"move"}


# -.-.-.-
def _frame_topology_is_current(frame: FrameSnapshot) -> bool:
    """Require a captured token and a matching live topology before visual input."""
    captured = str(frame.topology_token or "").strip()
    if not captured:
        return False
    live = str(current_topology_token() or "").strip()
    if not live:
        return False
    return captured == live


# -.-.-.-
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

    if action.action in _VISUAL_ACTIONS and not _frame_topology_is_current(frame):
        return (
            "Display topology could not be verified against this frame. Action was not dispatched; re-observe the desktop first.",
            True,
        )

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

    with per_monitor_dpi_context():
        result = computer_control(parameters=params, player=player)
    return str(result or "Done."), action.action in _CHANGE_EXPECTED_ACTIONS
