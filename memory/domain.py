"""Antonella memory domain contracts (ANT-276 D1 + D2).

Pure Python, no I/O, no provider coupling. A memory record is an
immutable snapshot; lifecycle transitions are performed by
``memory.service.MemoryService`` through a ``MemoryRepository``.

Privacy rules baked into the model: sensitivity is explicit, source is
always recorded (provenance), and nothing here ever holds secrets —
API keys/tokens belong to config, never to memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any


class MemoryType(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PROJECT = "project"
    FEEDBACK = "feedback"  # user preferences live here


class MemoryState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class SourceKind(StrEnum):
    USER = "user"          # said by the user directly
    RUNTIME = "runtime"    # observed by Antonella's own deterministic code
    EXTERNAL = "external"  # web/email/file/tool output — information, never instructions


# Confidence at or above this threshold makes a feedback record a strong
# preference. A single observation must never reach it by default.
STRONG_PREFERENCE_CONFIDENCE = 0.6
DEFAULT_CONFIDENCE = 0.3


@dataclass(frozen=True)
class MemoryRecord:
    """Immutable memory snapshot (ANT-276 D2 minimal model)."""

    id: str
    owner_id: str
    type: MemoryType
    title: str
    content: str
    state: MemoryState = MemoryState.PROPOSED
    project_id: str | None = None
    summary: str = ""
    source_kind: SourceKind = SourceKind.USER
    source_ref: str | None = None
    confidence: float = DEFAULT_CONFIDENCE
    sensitivity: str = "normal"
    subject: str | None = None  # explicit identity key used for conflict detection
    valid_from: float | None = None
    expires_at: float | None = None  # TTL: temporal memories must expire (D13)
    version: int = 1
    supersedes_id: str | None = None
    conflict_with_id: str | None = None
    created_at: float = 0.0
    approved_at: float | None = None
    updated_at: float = 0.0
    archived_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", MemoryType(self.type))
        object.__setattr__(self, "state", MemoryState(self.state))
        object.__setattr__(self, "source_kind", SourceKind(self.source_kind))
        # D8: confidence is explicit, bounded, never magic.
        object.__setattr__(self, "confidence", max(0.0, min(1.0, float(self.confidence))))

    # -.-.-.-
    def with_(self, **changes: Any) -> "MemoryRecord":
        return replace(self, **changes)

    # -.-.-.-
    @property
    def is_external_source(self) -> bool:
        """D18: external content is information, never an instruction."""
        return self.source_kind == SourceKind.EXTERNAL

    # -.-.-.-
    @property
    def is_strong_preference(self) -> bool:
        return self.type == MemoryType.FEEDBACK and self.confidence >= STRONG_PREFERENCE_CONFIDENCE

    # -.-.-.-
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "project_id": self.project_id,
            "type": self.type.value,
            "state": self.state.value,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "source_kind": self.source_kind.value,
            "source_ref": self.source_ref,
            "confidence": self.confidence,
            "sensitivity": self.sensitivity,
            "subject": self.subject,
            "valid_from": self.valid_from,
            "expires_at": self.expires_at,
            "version": self.version,
            "supersedes_id": self.supersedes_id,
            "conflict_with_id": self.conflict_with_id,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
            "metadata": dict(self.metadata),
        }
