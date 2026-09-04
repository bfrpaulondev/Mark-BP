from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class FrameSnapshot:
    sequence: int
    timestamp: float
    left: int
    top: int
    monitor_width: int
    monitor_height: int
    image_width: int
    image_height: int
    monitor_index: int
    change_score: float
    jpeg_bytes: bytes

    def to_screen_coordinates(self, x: int, y: int) -> tuple[int, int]:
        if self.image_width <= 0 or self.image_height <= 0:
            return self.left, self.top
        scaled_x = self.left + round((x / self.image_width) * self.monitor_width)
        scaled_y = self.top + round((y / self.image_height) * self.monitor_height)
        max_x = self.left + max(0, self.monitor_width - 1)
        max_y = self.top + max(0, self.monitor_height - 1)
        return (
            min(max(scaled_x, self.left), max_x),
            min(max(scaled_y, self.top), max_y),
        )


@dataclass
class ComputerAction:
    action: str
    description: str = ""
    x: int | None = None
    y: int | None = None
    direction: str = "down"
    amount: int = 3
    text: str = ""
    keys: str = ""
    key: str = ""
    seconds: float = 0.8
    confidence: float = 0.0
    risk: str = "low"
    result: str = ""

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ComputerAction":
        action = str(payload.get("action") or "fail").strip().lower()
        return cls(
            action=action,
            description=str(payload.get("description") or "").strip(),
            x=_optional_int(payload.get("x")),
            y=_optional_int(payload.get("y")),
            direction=str(payload.get("direction") or "down").strip().lower(),
            amount=max(1, min(12, _safe_int(payload.get("amount"), 3))),
            text=str(payload.get("text") or ""),
            keys=str(payload.get("keys") or ""),
            key=str(payload.get("key") or ""),
            seconds=max(0.1, min(10.0, _safe_float(payload.get("seconds"), 0.8))),
            confidence=max(0.0, min(1.0, _safe_float(payload.get("confidence"), 0.0))),
            risk=str(payload.get("risk") or "low").strip().lower(),
            result=str(payload.get("result") or "").strip(),
        )

    def history_line(self) -> str:
        details = self.description or self.result or self.action
        return f"{self.action}: {details[:180]}"


@dataclass
class SessionState:
    state: str = "idle"
    objective: str = ""
    target_window: str = ""
    requested_monitor: int | str | None = None
    cost_mode: str = "economy"
    provider: str = ""
    model: str = ""
    step: int = 0
    model_calls: int = 0
    visual_updates: int = 0
    last_action: str = ""
    last_error: str = ""
    result: str = ""
    awaiting_approval: bool = False
    monitor_index: int | None = None
    history: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "objective": self.objective,
            "target_window": self.target_window,
            "requested_monitor": self.requested_monitor,
            "cost_mode": self.cost_mode,
            "provider": self.provider,
            "model": self.model,
            "step": self.step,
            "model_calls": self.model_calls,
            "visual_updates": self.visual_updates,
            "last_action": self.last_action,
            "last_error": self.last_error,
            "result": self.result,
            "awaiting_approval": self.awaiting_approval,
            "monitor_index": self.monitor_index,
            "history": list(self.history[-12:]),
        }


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
