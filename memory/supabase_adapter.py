"""Supabase/Postgres adapter for the memory repository (ANT-276 D6).

Implements the ``MemoryRepository`` protocol over any injected client
that speaks the supabase-py fluent table API::

    client.table("memories").select("*").eq("owner_id", x).execute()

The client is ALWAYS injected — this module never builds credentials,
never reads keys, and fails closed when environment configuration is
missing. Tested against an in-memory fake client; real validation needs
a Supabase project (READY FOR SUPABASE VALIDATION).
"""

from __future__ import annotations

import os
from typing import Any

from memory.domain import MemoryRecord, MemoryState, MemoryType
from memory.repository import MemoryQuery

TABLE = "memories"
ENV_URL = "ANTONELLA_SUPABASE_URL"
ENV_KEY = "ANTONELLA_SUPABASE_KEY"


class SupabaseConfigurationError(RuntimeError):
    """Raised when Supabase env configuration is missing — never guess."""


def client_from_env() -> Any:
    """Build a supabase client strictly from environment variables."""
    url = os.environ.get(ENV_URL)
    key = os.environ.get(ENV_KEY)
    if not url or not key:
        raise SupabaseConfigurationError(
            f"missing Supabase configuration: set {ENV_URL} and {ENV_KEY}"
        )
    try:
        from supabase import create_client  # optional dependency

        return create_client(url, key)
    except ImportError as exc:
        raise SupabaseConfigurationError(
            "supabase package not installed; install it or inject a client"
        ) from exc


class SupabaseMemoryRepository:
    def __init__(self, client: Any):
        self._client = client

    # -.-.-.-
    def _record_from_row(self, row: dict[str, Any]) -> MemoryRecord:
        return MemoryRecord(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            type=MemoryType(row["type"]),
            title=str(row.get("title") or ""),
            content=str(row.get("content") or ""),
            state=MemoryState(row.get("state") or "proposed"),
            project_id=row.get("project_id"),
            summary=str(row.get("summary") or ""),
            source_kind=row.get("source_kind") or "user",
            source_ref=row.get("source_ref"),
            confidence=float(row.get("confidence") or 0.0),
            sensitivity=str(row.get("sensitivity") or "normal"),
            subject=row.get("subject"),
            valid_from=row.get("valid_from"),
            expires_at=row.get("expires_at"),
            version=int(row.get("version") or 1),
            supersedes_id=row.get("supersedes_id"),
            conflict_with_id=row.get("conflict_with_id"),
            created_at=float(row.get("created_at") or 0.0),
            approved_at=row.get("approved_at"),
            updated_at=float(row.get("updated_at") or 0.0),
            archived_at=row.get("archived_at"),
        )

    # -.-.-.-
    def save(self, record: MemoryRecord) -> None:
        payload = record.to_dict()
        self._client.table(TABLE).upsert(payload).execute()

    # -.-.-.-
    def get(self, record_id: str, owner_id: str) -> MemoryRecord | None:
        response = (
            self._client.table(TABLE)
            .select("*")
            .eq("id", record_id)
            .eq("owner_id", owner_id)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return self._record_from_row(rows[0]) if rows else None

    # -.-.-.-
    def query(self, query: MemoryQuery) -> list[MemoryRecord]:
        """Server-side owner/state/type filters; lexical narrowing and
        expiry happen here (deterministically) like the in-memory store.
        Row cap keeps the context budget honest (D17)."""
        builder = self._client.table(TABLE).select("*").eq("owner_id", query.owner_id)
        if query.project_id is not None:
            builder = builder.eq("project_id", query.project_id)
        builder = builder.eq("state", query.state.value)
        if query.type is not None:
            builder = builder.eq("type", query.type.value)
        response = builder.limit(500).execute()
        rows = getattr(response, "data", None) or []
        now = query.now if query.now is not None else _default_now()

        results: list[MemoryRecord] = []
        for row in rows:
            record = self._record_from_row(row)
            if not query.include_expired and record.expires_at is not None and record.expires_at <= now:
                continue
            if query.text:
                needle = query.text.casefold()
                haystack = f"{record.title}\n{record.summary}\n{record.content}".casefold()
                if needle not in haystack:
                    continue
            results.append(record)
        results.sort(key=lambda r: (-r.confidence, -r.updated_at, r.id))
        return results

    # -.-.-.-
    def delete(self, record_id: str, owner_id: str) -> bool:
        existing = self.get(record_id, owner_id)
        if existing is None:
            return False
        self._client.table(TABLE).delete().eq("id", record_id).eq("owner_id", owner_id).execute()
        return True


def _default_now() -> float:
    import time

    return time.time()
