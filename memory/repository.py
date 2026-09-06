"""Memory repository contract and in-memory implementation (ANT-276 D6).

Provider-neutral and testable: services depend on the Protocol only.
The Supabase/Postgres adapter lands as a separate slice (D3–D5) behind
the same interface.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from memory.domain import MemoryRecord, MemoryState, MemoryType


@dataclass(frozen=True)
class MemoryQuery:
    owner_id: str
    project_id: str | None = None
    type: MemoryType | None = None
    state: MemoryState = MemoryState.ACTIVE
    text: str | None = None  # lexical search over title/summary/content
    include_expired: bool = False
    now: float | None = None


@runtime_checkable
class MemoryRepository(Protocol):
    def save(self, record: MemoryRecord) -> None: ...

    def get(self, record_id: str, owner_id: str) -> MemoryRecord | None: ...

    def query(self, query: MemoryQuery) -> list[MemoryRecord]: ...

    def delete(self, record_id: str, owner_id: str) -> bool: ...


class InMemoryMemoryRepository:
    """Thread-safe in-memory store for tests and offline operation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, MemoryRecord] = {}

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    # -.-.-.-
    def save(self, record: MemoryRecord) -> None:
        with self._lock:
            self._records[record.id] = record

    # -.-.-.-
    def get(self, record_id: str, owner_id: str) -> MemoryRecord | None:
        with self._lock:
            record = self._records.get(record_id)
        # Owner isolation is enforced at the storage boundary too (D11).
        if record is None or record.owner_id != owner_id:
            return None
        return record

    # -.-.-.-
    def query(self, query: MemoryQuery) -> list[MemoryRecord]:
        with self._lock:
            records = list(self._records.values())

        now = query.now if query.now is not None else _default_now()
        results: list[MemoryRecord] = []
        for record in records:
            if record.owner_id != query.owner_id:
                continue  # hard owner isolation (D11)
            if query.project_id is not None and record.project_id != query.project_id:
                continue  # project isolation (D11)
            if record.state != query.state:
                continue
            if query.type is not None and record.type != query.type:
                continue
            if not query.include_expired and _is_expired(record, now):
                continue
            if query.text:
                needle = query.text.casefold()
                haystack = f"{record.title}\n{record.summary}\n{record.content}".casefold()
                if needle not in haystack:
                    continue
            results.append(record)

        # D16 deterministic ordering: confidence first, then recency.
        results.sort(key=lambda r: (-r.confidence, -r.updated_at, r.id))
        return results

    # -.-.-.-
    def delete(self, record_id: str, owner_id: str) -> bool:
        with self._lock:
            record = self._records.get(record_id)
            if record is None or record.owner_id != owner_id:
                return False
            del self._records[record_id]
            return True


def _default_now() -> float:
    import time

    return time.time()


def _is_expired(record: MemoryRecord, now: float) -> bool:
    return record.expires_at is not None and record.expires_at <= now


def all_records(repository: MemoryRepository) -> Iterable[MemoryRecord]:
    """Test/debug helper — only valid for the in-memory implementation."""
    if isinstance(repository, InMemoryMemoryRepository):
        with repository._lock:
            return list(repository._records.values())
    raise TypeError("all_records supports only InMemoryMemoryRepository")
