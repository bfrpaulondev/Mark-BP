from __future__ import annotations

from dataclasses import dataclass, field

from core.computer_use.contracts import ComputerAction, FrameSnapshot


_COORDINATE_ACTIONS = {"click", "double_click", "right_click", "move"}
_RETRY_SAFE_ACTIONS = {"scroll"}


@dataclass(frozen=True)
class RecoveryPolicy:
    """Deterministic bounds for visual recovery without delegating safety to a model."""

    max_recoveries: int = 6
    max_safe_action_retries: int = 1
    reacquire_timeout: float = 2.5
    min_settle_timeout: float = 0.7
    max_settle_timeout: float = 3.5

    # -.-.-.-
    @classmethod
    def for_step_budget(cls, max_steps: int) -> "RecoveryPolicy":
        bounded_steps = max(1, int(max_steps))
        return cls(max_recoveries=max(4, min(10, (bounded_steps // 2) + 2)))

    # -.-.-.-
    def settle_timeout(self, action: ComputerAction, no_change_streak: int = 0) -> float:
        base = {
            "click": 1.8,
            "double_click": 2.0,
            "right_click": 1.6,
            "scroll": 1.15,
            "type": 1.5,
            "smart_type": 1.7,
            "hotkey": 1.8,
            "press": 1.5,
        }.get(action.action, 1.0)
        adaptive = base + (max(0, int(no_change_streak)) * 0.35)
        return max(self.min_settle_timeout, min(self.max_settle_timeout, adaptive))


@dataclass
class RecoveryState:
    recoveries: int = 0
    safe_action_retries: int = 0
    no_change_streak: int = 0
    stale_replans: int = 0
    target_reacquisitions: int = 0
    last_reason: str = ""
    _action_retry_counts: dict[str, int] = field(default_factory=dict, repr=False)

    # -.-.-.-
    def note_visual_change(self, changed: bool) -> None:
        if changed:
            self.no_change_streak = 0
            self._action_retry_counts.clear()
        else:
            self.no_change_streak += 1

    # -.-.-.-
    def note_recovery(self, reason: str, *, kind: str = "generic") -> None:
        self.recoveries += 1
        self.last_reason = str(reason or "recovery")[:160]
        if kind == "stale":
            self.stale_replans += 1
        elif kind == "reacquire":
            self.target_reacquisitions += 1

    # -.-.-.-
    def can_recover(self, policy: RecoveryPolicy) -> bool:
        return self.recoveries < policy.max_recoveries

    # -.-.-.-
    def can_retry_action(self, action: ComputerAction, policy: RecoveryPolicy) -> bool:
        if action.action not in _RETRY_SAFE_ACTIONS:
            return False
        count = self._action_retry_counts.get(action.action, 0)
        return count < policy.max_safe_action_retries

    # -.-.-.-
    def note_action_retry(self, action: ComputerAction) -> None:
        self.safe_action_retries += 1
        self._action_retry_counts[action.action] = (
            self._action_retry_counts.get(action.action, 0) + 1
        )

    # -.-.-.-
    def snapshot(self) -> dict[str, int | str]:
        return {
            "recoveries": self.recoveries,
            "safe_action_retries": self.safe_action_retries,
            "no_change_streak": self.no_change_streak,
            "stale_replans": self.stale_replans,
            "target_reacquisitions": self.target_reacquisitions,
            "last_reason": self.last_reason,
        }


# -.-.-.-
def frame_is_superseded(planned: FrameSnapshot, latest: FrameSnapshot) -> bool:
    """Treat a newer emitted frame as a stale-plan boundary.

    Capture only emits meaningful visual/topology/geometry changes, while exact duplicate
    frames are suppressed. Therefore a newer sequence is enough to invalidate coordinates
    and other visual assumptions made against the planned frame.
    """

    if latest.sequence <= planned.sequence:
        return False
    return True


# -.-.-.-
def action_uses_planned_coordinates(action: ComputerAction) -> bool:
    return action.action in _COORDINATE_ACTIONS


# -.-.-.-
def target_scope_is_valid(frame: FrameSnapshot, target_window: str) -> bool:
    if not str(target_window or "").strip():
        return True
    return frame.capture_scope == "window"
