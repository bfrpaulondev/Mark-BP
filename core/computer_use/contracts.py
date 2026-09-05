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
    capture_scope: str = "monitor"
    pixel_savings: float = 0.0
    topology_token: str = ""
    dpi_x: int = 96
    dpi_y: int = 96
    scale_x: float = 1.0
    scale_y: float = 1.0
    monitor_device: str = ""
    monitor_primary: bool = False
    perception_digest: str = ""
    perception_keyframe: bool = True
    perception_duplicate: bool = False
    perception_distance: int | None = None

    def to_screen_coordinates(self, x: int, y: int) -> tuple[int, int]:
        """Map model-image pixels directly into physical virtual-desktop pixels.

        MSS captures physical pixels while the capture thread is per-monitor DPI aware,
        so DPI metadata is descriptive and must not be multiplied into coordinates again.
        """
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
    reobserve: bool = True
    # Local deterministic adapters may attach transient semantic context for
    # safety classification. It is intentionally not accepted from model
    # payloads and is never included in history_line()/SessionState evidence.
    safety_context: str = ""

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
            reobserve=_safe_bool(payload.get("reobserve"), True),
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
    batched_actions: int = 0
    saved_model_calls: int = 0
    capture_scope: str = "monitor"
    capture_savings_pct: int = 0
    perception_keyframes: int = 0
    perception_duplicates: int = 0
    local_perception_routes: int = 0
    perception_cache_hits: int = 0
    last_action: str = ""
    last_error: str = ""
    result: str = ""
    awaiting_approval: bool = False
    paused: bool = False
    target_locked: bool = False
    recovery_count: int = 0
    retry_count: int = 0
    no_change_streak: int = 0
    stale_replans: int = 0
    target_reacquisitions: int = 0
    last_recovery_reason: str = ""
    monitor_index: int | None = None
    history: list[str] = field(default_factory=list)
    telemetry_task_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    estimated_cost_usd: float | None = None
    known_cost_usd: float = 0.0
    cost_complete: bool = False

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
            "batched_actions": self.batched_actions,
            "saved_model_calls": self.saved_model_calls,
            "capture_scope": self.capture_scope,
            "capture_savings_pct": self.capture_savings_pct,
            "perception_keyframes": self.perception_keyframes,
            "perception_duplicates": self.perception_duplicates,
            "local_perception_routes": self.local_perception_routes,
            "perception_cache_hits": self.perception_cache_hits,
            "last_action": self.last_action,
            "last_error": self.last_error,
            "result": self.result,
            "awaiting_approval": self.awaiting_approval,
            "paused": self.paused,
            "target_locked": self.target_locked,
            "recovery_count": self.recovery_count,
            "retry_count": self.retry_count,
            "no_change_streak": self.no_change_streak,
            "stale_replans": self.stale_replans,
            "target_reacquisitions": self.target_reacquisitions,
            "last_recovery_reason": self.last_recovery_reason,
            "monitor_index": self.monitor_index,
            "history": list(self.history[-12:]),
            "telemetry_task_id": self.telemetry_task_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "known_cost_usd": self.known_cost_usd,
            "cost_complete": self.cost_complete,
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


def _safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return default
