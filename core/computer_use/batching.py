from __future__ import annotations

from core.computer_use.contracts import ComputerAction


MAX_ACTIONS_PER_PLAN = 3
_TEXT_ACTIONS = {"type", "smart_type"}
_SAFE_NAV_KEYS = {"tab", "left", "right", "up", "down", "home", "end"}
_SAFE_SELECT_ALL = {"ctrl+a", "command+a", "cmd+a"}


# -.-.-.-
def can_chain_without_reobserve(current: ComputerAction, following: ComputerAction) -> bool:
    """Return True only for deterministic low-risk continuations that do not need pixels."""
    if current.risk != "low" or following.risk != "low":
        return False

    if following.action not in _TEXT_ACTIONS:
        return False

    if current.action == "click":
        return current.x is not None and current.y is not None

    if current.action == "hotkey":
        keys = str(current.keys or "").lower().replace(" ", "")
        return keys in _SAFE_SELECT_ALL

    if current.action == "press":
        return str(current.key or "").strip().lower() in _SAFE_NAV_KEYS

    return False


# -.-.-.-
def sanitize_action_batch(actions: list[ComputerAction]) -> list[ComputerAction]:
    """Enforce local batching rules even if the model proposes an unsafe sequence."""
    if not actions:
        return []

    batch = actions[:MAX_ACTIONS_PER_PLAN]
    safe: list[ComputerAction] = []

    for index, action in enumerate(batch):
        safe.append(action)

        if action.action in {"done", "fail"}:
            break

        has_following = index + 1 < len(batch)
        if not has_following:
            action.reobserve = True
            break

        following = batch[index + 1]
        requested_chain = not action.reobserve
        if not requested_chain or not can_chain_without_reobserve(action, following):
            action.reobserve = True
            break

        action.reobserve = False

    if safe:
        last = safe[-1]
        if last.action not in {"done", "fail"}:
            last.reobserve = True

    return safe
