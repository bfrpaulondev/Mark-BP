"""Supabase/Postgres adapter for the memory repository (ANT-276 D6).

Implements the ``MemoryRepository`` protocol over any injected client
that speaks the supabase-py fluent table API::

    client.table("memories").select("*").eq("owner_id", x).execute()

The client is ALWAYS injected — this module never invents credentials
and fails closed when environment configuration is missing. Runtime
records use epoch seconds while Postgres uses ``timestamptz``; this
adapter performs that boundary conversion explicitly so the fake client
and a real PostgREST response have the same semantics.
"""

from __future__ import annotations

import os
import base64
import json
from uuid import UUID
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Any

from memory.domain import MemoryRecord, MemoryState, MemoryType
from memory.repository import MemoryQuery

TABLE = "memories"
ENV_URL = "ANTONELLA_SUPABASE_URL"
ENV_KEY = "ANTONELLA_SUPABASE_KEY"
_TIMESTAMP_FIELDS = (
    "valid_from",
    "expires_at",
    "created_at",
    "approved_at",
    "updated_at",
    "archived_at",
)


class SupabaseConfigurationError(RuntimeError):
    """Raised when Supabase env configuration is missing — never guess."""


ENV_ACCESS_TOKEN = "ANTONELLA_SUPABASE_ACCESS_TOKEN"
ENV_REFRESH_TOKEN = "ANTONELLA_SUPABASE_REFRESH_TOKEN"
ENV_FIELDS = (ENV_URL, ENV_KEY, ENV_ACCESS_TOKEN, ENV_REFRESH_TOKEN)


# -.-.-.-
def _jwt_claims(token: str) -> dict:
    """Inspect token shape only; authorization always requires server validation."""
    try:
        encoded = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not isinstance(claims, dict):
            raise ValueError()
        return claims
    except (ValueError, IndexError, UnicodeError):
        raise SupabaseConfigurationError("Invalid Supabase token format") from None


# -.-.-.-
def authenticated_owner_id(client: Any) -> str:
    """Bind the Data API session to a UUID validated by Supabase Auth."""
    session = client.auth.get_session()
    token = str(getattr(session, "access_token", "") or "")
    claims = _jwt_claims(token)
    if claims.get("role") != "authenticated":
        raise SupabaseConfigurationError("An authenticated user session is required")
    # get_user validates JWT with the Auth server; local JWT claims are not proof.
    response = client.auth.get_user(token)
    user = getattr(response, "user", None)
    try:
        owner = str(UUID(str(getattr(user, "id", ""))))
        subject = str(UUID(str(claims.get("sub", ""))))
    except ValueError:
        raise SupabaseConfigurationError("Authenticated owner must be a UUID") from None
    if owner != subject or getattr(user, "is_anonymous", False):
        raise SupabaseConfigurationError("A stable authenticated owner is required")
    return owner


# -.-.-.-
def client_from_env(*, env: Any = None, prefix: str = "ANTONELLA_SUPABASE") -> Any:
    """Build a desktop-safe user client; never accept privileged API keys.

    Session credentials come from the environment, never persisted by this
    module. Missing/partial/auth failures cannot silently enable persistence.
    """
    values = os.environ if env is None else env
    url, key, access, refresh = (
        str(values.get(f"{prefix}_{suffix}") or "").strip()
        for suffix in ("URL", "KEY", "ACCESS_TOKEN", "REFRESH_TOKEN")
    )
    if not all((url, key, access, refresh)):
        raise SupabaseConfigurationError("Supabase URL, public key and user session are required")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SupabaseConfigurationError("Supabase requires an HTTPS project URL")
    if not key.startswith("sb_publishable_"):
        if key.startswith("sb_secret_") or _jwt_claims(key).get("role") != "anon":
            raise SupabaseConfigurationError("Privileged Supabase keys are forbidden on desktop")
    if _jwt_claims(access).get("role") != "authenticated":
        raise SupabaseConfigurationError("An authenticated user access token is required")
    try:
        from supabase import create_client  # optional dependency
    except ImportError:
        raise SupabaseConfigurationError("Optional supabase package is unavailable") from None
    try:
        client = create_client(url, key)
        client.auth.set_session(access, refresh)
        authenticated_owner_id(client)
        return client
    except Exception:
        # No provider messages, URLs, tokens or response bodies cross this boundary.
        raise SupabaseConfigurationError("Supabase authenticated session initialization failed") from None


# -.-.-.-
def verify_memory_schema(client: Any, owner_id: str) -> None:
    """Check the exposed schema required by 0001 + 0005 without applying SQL.

    Column/table availability does not prove RLS, indexes or migration history.
    Actual owner isolation requires the separate two-session validator.
    """
    columns = {
        "memories": "id,owner_id,project_id,type,state,title,content,summary,source_kind,source_ref,confidence,sensitivity,subject,valid_from,expires_at,version,supersedes_id,conflict_with_id,created_at,approved_at,updated_at,archived_at,metadata",
        "memory_relations": "id,owner_id,from_memory,to_memory,relation,created_at",
        "memory_feedback": "id,owner_id,memory_id,helpful,note,created_at",
    }
    for table, fields in columns.items():
        client.table(table).select(fields).eq("owner_id", owner_id).limit(1).execute()


# -.-.-.-
def _timestamp_from_db(value: Any) -> float | None:
    """Normalize PostgREST timestamptz values to epoch seconds.

    Real Supabase responses normally return ISO-8601 strings. Tests and
    injected adapters may supply numeric epochs or ``datetime`` objects.
    Unknown/malformed values fail closed with ``ValueError`` instead of
    silently turning a temporal memory into a non-expiring one.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid memory timestamp")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid timestamptz returned by memory backend") from exc
    else:
        raise ValueError(f"unsupported timestamp type: {type(value).__name__}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return float(dt.timestamp())


# -.-.-.-
def _timestamp_to_db(value: Any) -> str | None:
    """Serialize an epoch/datetime as an explicit UTC ISO-8601 value."""
    epoch = _timestamp_from_db(value)
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


# -.-.-.-
def _payload_for_db(record: MemoryRecord) -> dict[str, Any]:
    payload = record.to_dict()
    for field in _TIMESTAMP_FIELDS:
        payload[field] = _timestamp_to_db(payload.get(field))
    # ``metadata`` is stored as jsonb by migration 0005. Keep a fresh dict
    # to prevent a client implementation from mutating the domain snapshot.
    payload["metadata"] = dict(record.metadata)
    return payload


class SupabaseMemoryRepository:
    def __init__(self, client: Any, *, owner_id: str | None = None):
        self._client = client
        self._owner_id = owner_id

    # -.-.-.-
    def _ensure_owner(self, owner_id: str) -> None:
        if self._owner_id is not None:
            if owner_id != self._owner_id or authenticated_owner_id(self._client) != self._owner_id:
                raise SupabaseConfigurationError("Memory owner/session mismatch")

    # -.-.-.-
    def _record_from_row(self, row: dict[str, Any]) -> MemoryRecord:
        created_at = _timestamp_from_db(row.get("created_at"))
        updated_at = _timestamp_from_db(row.get("updated_at"))
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
            valid_from=_timestamp_from_db(row.get("valid_from")),
            expires_at=_timestamp_from_db(row.get("expires_at")),
            version=int(row.get("version") or 1),
            supersedes_id=row.get("supersedes_id"),
            conflict_with_id=row.get("conflict_with_id"),
            created_at=created_at if created_at is not None else 0.0,
            approved_at=_timestamp_from_db(row.get("approved_at")),
            updated_at=updated_at if updated_at is not None else 0.0,
            archived_at=_timestamp_from_db(row.get("archived_at")),
            metadata=dict(row.get("metadata") or {}),
        )

    # -.-.-.-
    def save(self, record: MemoryRecord) -> None:
        self._ensure_owner(record.owner_id)
        self._client.table(TABLE).upsert(_payload_for_db(record)).execute()

    # -.-.-.-
    def get(self, record_id: str, owner_id: str) -> MemoryRecord | None:
        self._ensure_owner(owner_id)
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
        self._ensure_owner(query.owner_id)
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


# -.-.-.-
def _default_now() -> float:
    import time

    return time.time()
