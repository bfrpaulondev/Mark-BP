"""Central runtime state model for the Antonella UI (ANT-268).

Pure Python module: no Qt imports, no engine imports. The UI only *observes*
values produced here; it never infers operational state from log strings,
prompt text or tool names. Engines keep calling the legacy string-based
``set_state(...)`` API, which is normalized into this model before it
reaches any widget.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class UiState(StrEnum):
    """Canonical operational states rendered by the UI.

    The first block follows the approved ANT-268 state vocabulary. The
    legacy block keeps engine-emitted strings working unchanged until the
    runtime migrates to the structured model (compatibility first, no
    mass rename).
    """

    # Canonical operational states
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    OBSERVING = "OBSERVING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    # Legacy compat states still emitted by the engines
    INITIALISING = "INITIALISING"
    SPEAKING = "SPEAKING"
    SLEEPING = "SLEEPING"
    MUTED = "MUTED"


# Legacy engine strings that carry the same meaning as a canonical state.
_LEGACY_ALIASES: dict[str, UiState] = {
    "PROCESSING": UiState.EXECUTING,
    "READY": UiState.IDLE,
    "STANDBY": UiState.IDLE,
    "AWAITING_APPROVAL": UiState.WAITING_APPROVAL,
    "PENDING_APPROVAL": UiState.WAITING_APPROVAL,
    "ERROR": UiState.FAILED,
    "ABORTED": UiState.CANCELLED,
}

# -.-.-.-
STATE_LABELS_PT: dict[UiState, str] = {
    UiState.IDLE: "PRONTA",
    UiState.LISTENING: "A OUVIR",
    UiState.THINKING: "A PENSAR",
    UiState.OBSERVING: "A OBSERVAR",
    UiState.EXECUTING: "A EXECUTAR",
    UiState.VERIFYING: "A VERIFICAR",
    UiState.RECOVERING: "A RECUPERAR",
    UiState.WAITING_APPROVAL: "A AGUARDAR APROVAÇÃO",
    UiState.COMPLETED: "CONCLUÍDO",
    UiState.FAILED: "FALHOU",
    UiState.CANCELLED: "CANCELADO",
    # Legacy states keep their established wording
    UiState.INITIALISING: "A INICIAR",
    UiState.SPEAKING: "A RESPONDER",
    UiState.SLEEPING: "EM ESPERA",
    UiState.MUTED: "MICROFONE EM PAUSA",
}

# -.-.-.-
def state_label_pt(state: UiState) -> str:
    """Return the pt-PT label for a state; every member must have one."""
    return STATE_LABELS_PT[state]


# -.-.-.-
def normalize_state(value: UiState | str | None) -> UiState:
    """Normalize any engine-emitted state value into a UiState.

    Total and fail-closed: unknown or empty values fall back to IDLE
    instead of leaking raw strings into widget logic.
    """
    if isinstance(value, UiState):
        return value
    if not isinstance(value, str):
        return UiState.IDLE
    text = value.strip().upper()
    if not text:
        return UiState.IDLE
    try:
        return UiState(text)
    except ValueError:
        pass
    if text in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[text]
    return UiState.IDLE


@dataclass(frozen=True)
class UiRuntimeState:
    """Immutable observation of what the runtime is doing right now.

    Widgets consume this snapshot as-is; they do not reinterpret it.
    Only technical metadata belongs here — never secrets, private text
    or clipboard content.
    """

    state: UiState = UiState.IDLE
    task_id: str | None = None
    task_name: str | None = None
    progress: int | None = None
    current_step: str | None = None
    tool: str | None = None
    provider: str | None = None
    model: str | None = None
    target_window: str | None = None
    target_monitor: str | None = None
    verified: bool | None = None
    error: str | None = None
    approval: str | None = None
    model_calls: int | None = None
    calls_saved: int | None = None
    estimated_cost: float | None = None
    elapsed: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", normalize_state(self.state))
        if self.progress is not None:
            object.__setattr__(self, "progress", max(0, min(100, int(self.progress))))

    # -.-.-.-
    @property
    def label_pt(self) -> str:
        return state_label_pt(self.state)

    # -.-.-.-
    def with_state(self, state: UiState | str) -> "UiRuntimeState":
        """Return a copy moved to the given state (convenience for engines)."""
        return UiRuntimeState(**{**self.to_dict(), "state": normalize_state(state)})

    # -.-.-.-
    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "progress": self.progress,
            "current_step": self.current_step,
            "tool": self.tool,
            "provider": self.provider,
            "model": self.model,
            "target_window": self.target_window,
            "target_monitor": self.target_monitor,
            "verified": self.verified,
            "error": self.error,
            "approval": self.approval,
            "model_calls": self.model_calls,
            "calls_saved": self.calls_saved,
            "estimated_cost": self.estimated_cost,
            "elapsed": self.elapsed,
        }
