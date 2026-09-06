"""Memory bootstrap: optional when absent, fail closed when configured but broken."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from memory.repository import InMemoryMemoryRepository
from memory.service import MemoryService
from memory.supabase_adapter import (ENV_FIELDS, SupabaseMemoryRepository,
    authenticated_owner_id, client_from_env, verify_memory_schema)


@dataclass(frozen=True)
class MemoryStack:
    service: MemoryService | None
    repository: Any
    backend: str
    fallback_reason: str | None = None
    owner_id: str = "local"
    status: str = "NOT CONFIGURED"
    persistent: bool = False


# -.-.-.-
def create_memory_stack() -> MemoryStack:
    """Environment is the explicit contract; no unused config argument.

    Any supplied Supabase field signals persistence intent, including partial
    or whitespace configuration. Only fully absent configuration uses InMemory.
    """
    if not any(name in os.environ for name in ENV_FIELDS):
        repo = InMemoryMemoryRepository()
        return MemoryStack(MemoryService(repo), repo, "inmemory",
                           "Supabase not configured; session-only memory")
    try:
        client = client_from_env()
        owner_id = authenticated_owner_id(client)
        verify_memory_schema(client, owner_id)
        repo = SupabaseMemoryRepository(client, owner_id=owner_id)
        return MemoryStack(MemoryService(repo), repo, "supabase",
                           owner_id=owner_id, status="READY", persistent=True)
    except Exception:
        # Configured persistence failures must never become ephemeral writes.
        return MemoryStack(None, None, "unavailable",
                           "Configured Supabase failed; memory operations disabled",
                           owner_id="", status="CONFIGURED BUT FAILED")
