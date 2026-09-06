"""Persistent task model (ANT-278 F1, F2, F3).

Pure dataclasses with round-trip ``to_dict``/``from_dict``: every task
survives process restart because its whole state is serialisable — the
store decides where those dictionaries live (memory now, cloud later).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

TERMINAL_STATES = frozenset({"completed", "failed", "cancelled", "expired"})


class TaskState(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class TaskStep:
    """One effectful unit of work. ``idempotency_key`` (F5) makes every
    effectful step replay-safe: the same key never executes twice."""

    name: str
    action: dict[str, Any]
    idempotency_key: str
    risk: str = "low"  # safe | medium | dangerous — dangerous never auto-retries (F8)
    max_retries: int = 2
    # T2: delivery ≠ verification. A step that carries a verifiable effect
    # only becomes "done" with delivered AND verified; otherwise it parks
    # in awaiting_verification / awaiting_approval / needs_review.
    requires_verification: bool = False
    state: str = "pending"  # pending | done | failed | awaiting_verification | awaiting_approval | needs_review | cancelled
    outcome: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "action": dict(self.action),
            "idempotency_key": self.idempotency_key,
            "risk": self.risk,
            "max_retries": self.max_retries,
            "requires_verification": self.requires_verification,
            "state": self.state,
            "outcome": dict(self.outcome),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskStep":
        return cls(
            name=str(data["name"]),
            action=dict(data.get("action") or {}),
            idempotency_key=str(data["idempotency_key"]),
            risk=str(data.get("risk") or "low"),
            max_retries=int(data.get("max_retries") or 2),
            requires_verification=bool(data.get("requires_verification") or False),
            state=str(data.get("state") or "pending"),
            outcome=dict(data.get("outcome") or {}),
        )


@dataclass
class Task:
    id: str
    owner_id: str
    title: str
    steps: list[TaskStep]
    state: TaskState = TaskState.CREATED
    project_id: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    error: str | None = None
    completed_keys: list[str] = field(default_factory=list)  # F4/F5 checkpoint
    approval_request_id: str | None = None  # T3: bound to the canonical approval manager

    # -.-.-.-
    @property
    def is_terminal(self) -> bool:
        return self.state.value in TERMINAL_STATES

    # -.-.-.-
    def with_(self, **changes: Any) -> "Task":
        return replace(self, **changes)

    # -.-.-.-
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "title": self.title,
            "project_id": self.project_id,
            "state": self.state.value,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "completed_keys": list(self.completed_keys),
            "approval_request_id": self.approval_request_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            id=str(data["id"]),
            owner_id=str(data["owner_id"]),
            title=str(data["title"]),
            project_id=data.get("project_id"),
            state=TaskState(data.get("state") or "created"),
            steps=[TaskStep.from_dict(step) for step in data.get("steps") or []],
            created_at=float(data.get("created_at") or 0.0),
            updated_at=float(data.get("updated_at") or 0.0),
            error=data.get("error"),
            completed_keys=list(data.get("completed_keys") or []),
            approval_request_id=data.get("approval_request_id"),
        )


@dataclass
class TaskCheckpoint:
    """F4: persisted after every effectful step — a restarted task never
    repeats an effect that a checkpoint already recorded."""

    task_id: str
    completed_keys: list[str]
    saved_at: float

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "completed_keys": list(self.completed_keys), "saved_at": self.saved_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskCheckpoint":
        return cls(
            task_id=str(data["task_id"]),
            completed_keys=list(data.get("completed_keys") or []),
            saved_at=float(data.get("saved_at") or 0.0),
        )


@dataclass
class TaskEvent:
    timestamp: float
    kind: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "kind": self.kind, "message": self.message}
