"""Memory service lifecycle (ANT-276 D7, D8, D9, D12–D15, D17, D18).

Rules that never bend:
- nothing becomes ACTIVE without an explicit approve;
- a new proposal about an occupied subject never silently overwrites the
  active record (D12: conflict + review, or explicit supersession);
- temporal memories expire (D13) and external content stays information
  (D18) — retrieval flags it, it never becomes an instruction;
- forgetting is explicit: archive (soft, reversible) or forget (hard).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from memory.domain import (
    DEFAULT_CONFIDENCE,
    MemoryRecord,
    MemoryState,
    MemoryType,
    SourceKind,
    STRONG_PREFERENCE_CONFIDENCE,
)
from memory.repository import MemoryQuery, MemoryRepository


@dataclass(frozen=True)
class RetrievalHit:
    """A retrieval result: record plus prompt-safety flags (D16/D18)."""

    record: MemoryRecord
    is_external: bool

    def as_prompt_payload(self) -> dict[str, Any]:
        """Context-budget-safe payload for prompt builders (D17).

        External content is labelled as information so prompt builders
        never mistake it for an instruction.
        """
        return {
            "id": self.record.id,
            "type": self.record.type.value,
            "title": self.record.title,
            "summary": self.record.summary or self.record.content[:280],
            "confidence": self.record.confidence,
            "external_information": self.is_external,
        }


class MemoryService:
    def __init__(self, repository: MemoryRepository, clock=None):
        self._repo = repository
        self._clock = clock or time.time

    # -.-.-.-
    def _now(self) -> float:
        return float(self._clock())

    # -.-.-.-
    @staticmethod
    def _subject(record: MemoryRecord) -> str:
        return (record.subject or record.title).strip().casefold()

    # -.-.-.-
    def _active_subject_matches(self, record: MemoryRecord) -> list[MemoryRecord]:
        subject = self._subject(record)
        return [
            candidate
            for candidate in self._repo.query(
                MemoryQuery(
                    owner_id=record.owner_id,
                    project_id=record.project_id,
                    state=MemoryState.ACTIVE,
                )
            )
            if candidate.type == record.type and self._subject(candidate) == subject
        ]

    # -.-.-.-
    def _validate_supersession_target(self, record: MemoryRecord) -> MemoryRecord:
        """Fail closed if a supersession target is stale or unrelated.

        A caller cannot retire an arbitrary memory by supplying its id. The
        target must still be ACTIVE and must represent the same owner-scoped
        project/type/subject at the moment of activation.
        """
        if not record.supersedes_id:
            raise ValueError("supersession target is missing")
        previous = self._repo.get(record.supersedes_id, record.owner_id)
        if previous is None:
            raise ValueError("supersession target does not exist for this owner")
        if previous.state is not MemoryState.ACTIVE:
            raise ValueError("supersession target is no longer active")
        if previous.type != record.type:
            raise ValueError("supersession target has a different memory type")
        if previous.project_id != record.project_id:
            raise ValueError("supersession target belongs to a different project")
        if self._subject(previous) != self._subject(record):
            raise ValueError("supersession target has a different subject")
        return previous

    # -.-.-.-
    def propose(
        self,
        *,
        owner_id: str,
        type_: MemoryType | str,
        title: str,
        content: str,
        project_id: str | None = None,
        summary: str = "",
        source_kind: SourceKind | str = SourceKind.USER,
        source_ref: str | None = None,
        confidence: float = DEFAULT_CONFIDENCE,
        subject: str | None = None,
        supersedes_id: str | None = None,
        expires_at: float | None = None,
        sensitivity: str = "normal",
        version: int = 1,
    ) -> MemoryRecord:
        """Create a PROPOSED memory. Never active by itself (D7).

        D12: when an active record already occupies the same subject and no
        explicit ``supersedes_id`` is given, the proposal is stored with
        ``conflict_with_id`` and stays proposed — review required, never a
        silent overwrite.
        """
        now = self._now()
        normalized_type = MemoryType(type_)
        normalized_subject = (subject or title).strip().casefold()
        conflict_with_id: str | None = None
        if supersedes_id is None:
            for record in self._repo.query(
                MemoryQuery(owner_id=owner_id, project_id=project_id, state=MemoryState.ACTIVE)
            ):
                if record.type == normalized_type and self._subject(record) == normalized_subject:
                    conflict_with_id = record.id
                    break

        record = MemoryRecord(
            id=uuid.uuid4().hex,
            owner_id=owner_id,
            type=normalized_type,
            title=title,
            content=content,
            state=MemoryState.PROPOSED,
            project_id=project_id,
            summary=summary,
            source_kind=SourceKind(source_kind),
            source_ref=source_ref,
            confidence=confidence,
            subject=normalized_subject,
            supersedes_id=supersedes_id,
            conflict_with_id=conflict_with_id,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            sensitivity=sensitivity,
            version=version,
        )
        if supersedes_id is not None:
            self._validate_supersession_target(record)
        self._repo.save(record)
        return record

    # -.-.-.-
    def approve(self, record_id: str, *, owner_id: str) -> MemoryRecord:
        """Approve a proposal; an explicit supersession retires the old one.

        M1: an unresolved conflict (``conflict_with_id`` set) can NEVER be
        approved normally — it must go through ``resolve_conflict`` first.
        Approval also revalidates current active state so a stale proposal
        cannot create two active memories for the same subject.
        """
        record = self._require(record_id, owner_id)
        if record.state is not MemoryState.PROPOSED:
            raise ValueError(f"only proposed memories can be approved (state={record.state.value})")
        if record.conflict_with_id is not None:
            raise ValueError(
                "unresolved conflict: call resolve_conflict() before approval "
                f"(conflicts with {record.conflict_with_id})"
            )

        previous: MemoryRecord | None = None
        if record.supersedes_id:
            previous = self._validate_supersession_target(record)
            unexpected = [
                item for item in self._active_subject_matches(record) if item.id != previous.id
            ]
            if unexpected:
                raise ValueError("memory subject changed while awaiting approval; review required")
        elif self._active_subject_matches(record):
            raise ValueError("memory subject became occupied while awaiting approval; review required")

        now = self._now()
        approved = record.with_(state=MemoryState.ACTIVE, approved_at=now, updated_at=now)
        self._repo.save(approved)
        if previous is not None:
            self._repo.save(previous.with_(state=MemoryState.SUPERSEDED, updated_at=now))
        return approved

    # -.-.-.-
    def resolve_conflict(
        self,
        record_id: str,
        *,
        owner_id: str,
        decision: str,
    ) -> MemoryRecord:
        """Explicit conflict resolution (M1): keep_existing | replace_existing | reject_new.

        - keep_existing / reject_new: archive the proposal (the active
          memory stays untouched; the decision is recorded in metadata);
        - replace_existing: converts the conflict into an explicit
          supersession — the proposal stays proposed and ``approve()``
          then retires the old record after revalidating it.
        """
        if decision not in ("keep_existing", "replace_existing", "reject_new"):
            raise ValueError(f"unknown conflict decision: {decision}")
        record = self._require(record_id, owner_id)
        if record.state is not MemoryState.PROPOSED:
            raise ValueError("only proposed memories can have a conflict resolved")
        if record.conflict_with_id is None:
            raise ValueError("record has no conflict to resolve")
        now = self._now()

        if decision == "replace_existing":
            resolved = record.with_(
                supersedes_id=record.conflict_with_id,
                conflict_with_id=None,
                updated_at=now,
            )
            self._validate_supersession_target(resolved)
        else:
            resolved = record.with_(
                state=MemoryState.ARCHIVED,
                archived_at=now,
                updated_at=now,
                conflict_with_id=None,
                metadata={**record.metadata, "conflict_resolution": decision},
            )
        self._repo.save(resolved)
        return resolved

    # -.-.-.-
    def retrieve(
        self,
        *,
        owner_id: str,
        project_id: str | None = None,
        type_: MemoryType | str | None = None,
        text: str | None = None,
        top_k: int = 8,
        now: float | None = None,
    ) -> list[RetrievalHit]:
        """Hybrid-ish retrieval (D16) under a context budget (D17).

        Only ACTIVE, non-expired records; deterministic ordering
        (confidence, then recency); bounded by ``top_k``. External sources
        are flagged as information, never instructions (D18).
        """
        query = MemoryQuery(
            owner_id=owner_id,
            project_id=project_id,
            type=MemoryType(type_) if type_ else None,
            state=MemoryState.ACTIVE,
            text=text,
            now=now if now is not None else self._now(),
        )
        return [
            RetrievalHit(record=record, is_external=record.is_external_source)
            for record in self._repo.query(query)[: max(0, top_k)]
        ]

    # -.-.-.-
    def supersede(
        self,
        record_id: str,
        *,
        owner_id: str,
        content: str,
        title: str | None = None,
        summary: str = "",
        confidence: float | None = None,
    ) -> MemoryRecord:
        """Explicit versioned supersession (D12/D15) — proposal, not auto."""
        record = self._require(record_id, owner_id)
        if record.state is not MemoryState.ACTIVE:
            raise ValueError("only active memories can be superseded")
        return self.propose(
            owner_id=owner_id,
            type_=record.type,
            title=title or record.title,
            content=content,
            project_id=record.project_id,
            summary=summary or record.summary,
            source_kind=record.source_kind,
            source_ref=record.source_ref,
            confidence=record.confidence if confidence is None else confidence,
            subject=record.subject,
            supersedes_id=record.id,
            expires_at=record.expires_at,
            sensitivity=record.sensitivity,
            version=record.version + 1,
        )

    # -.-.-.-
    def archive(self, record_id: str, *, owner_id: str) -> MemoryRecord:
        """Soft delete (D14) — reversible."""
        record = self._require(record_id, owner_id)
        if record.state not in (MemoryState.ACTIVE, MemoryState.PROPOSED, MemoryState.APPROVED):
            raise ValueError(f"cannot archive memory in state {record.state.value}")
        now = self._now()
        archived = record.with_(state=MemoryState.ARCHIVED, archived_at=now, updated_at=now)
        self._repo.save(archived)
        return archived

    # -.-.-.-
    def restore(self, record_id: str, *, owner_id: str) -> MemoryRecord:
        """D14 recovery: an archived memory goes back to review, not to active."""
        record = self._require(record_id, owner_id)
        if record.state is not MemoryState.ARCHIVED:
            raise ValueError("only archived memories can be restored")
        restored = record.with_(state=MemoryState.PROPOSED, archived_at=None, updated_at=self._now())
        self._repo.save(restored)
        return restored

    # -.-.-.-
    def forget(self, record_id: str, *, owner_id: str) -> bool:
        """Permanent removal (D14) — the user's right to be forgotten."""
        return self._repo.delete(record_id, owner_id)

    # -.-.-.-
    def explain_source(self, record_id: str, *, owner_id: str) -> dict[str, Any]:
        """Provenance chain (D15): where a memory came from, full history."""
        chain: list[dict[str, Any]] = []
        current: MemoryRecord | None = self._require(record_id, owner_id)
        while current is not None:
            chain.append(
                {
                    "id": current.id,
                    "version": current.version,
                    "state": current.state.value,
                    "source_kind": current.source_kind.value,
                    "source_ref": current.source_ref,
                    "title": current.title,
                    "created_at": current.created_at,
                }
            )
            current = (
                self._repo.get(current.supersedes_id, owner_id) if current.supersedes_id else None
            )
        return {"chain": chain}

    # -.-.-.-
    def strong_preferences(self, *, owner_id: str, project_id: str | None = None) -> list[MemoryRecord]:
        """D9: only confidence-backed preferences; one observation never
        becomes a strong preference (default confidence is below threshold)."""
        return [
            record
            for record in self._repo.query(
                MemoryQuery(owner_id=owner_id, project_id=project_id, type=MemoryType.FEEDBACK)
            )
            if record.confidence >= STRONG_PREFERENCE_CONFIDENCE
        ]

    # -.-.-.-
    def expire(self, *, owner_id: str, now: float | None = None) -> list[str]:
        """D13: archive expired active memories (temporal facts die)."""
        now_value = now if now is not None else self._now()
        expired: list[str] = []
        for record in self._repo.query(
            MemoryQuery(owner_id=owner_id, state=MemoryState.ACTIVE, include_expired=True, now=now_value)
        ):
            if record.expires_at is not None and record.expires_at <= now_value:
                self._repo.save(
                    record.with_(
                        state=MemoryState.ARCHIVED,
                        archived_at=now_value,
                        updated_at=now_value,
                        metadata={**record.metadata, "expired": True},
                    )
                )
                expired.append(record.id)
        return expired

    # -.-.-.-
    def _require(self, record_id: str, owner_id: str) -> MemoryRecord:
        record = self._repo.get(record_id, owner_id)
        if record is None:
            raise KeyError(f"memory not found for this owner: {record_id}")
        return record
