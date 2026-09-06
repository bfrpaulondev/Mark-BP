"""Memory stack bootstrap (ANT-276 wiring R2).

Chooses the memory repository for the runtime:

- Supabase when ``ANTONELLA_SUPABASE_URL``/``KEY`` are set AND the
  optional client builds successfully;
- InMemory otherwise — Antonella NEVER breaks because Supabase is not
  configured (fail-closed on configuration errors, then graceful
  fallback with a reason).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memory.repository import MemoryRepository
from memory.service import MemoryService


@dataclass(frozen=True)
class MemoryStack:
    service: MemoryService
    repository: Any
    backend: str          # "supabase" | "inmemory"
    fallback_reason: str | None = None


def create_memory_stack(config: dict[str, Any] | None = None) -> MemoryStack:
    """Build the runtime memory stack (R2).

    Never raises for missing/invalid Supabase configuration: falls back
    to InMemory and records the reason. Only programming errors bubble.
    """
    from memory.repository import InMemoryMemoryRepository
    from memory.service import MemoryService

    repo: MemoryRepository = InMemoryMemoryRepository()
    try:
        from memory.supabase_adapter import (
            SupabaseConfigurationError,
            SupabaseMemoryRepository,
            client_from_env,
        )

        try:
            repo = SupabaseMemoryRepository(client_from_env())
            return MemoryStack(
                service=MemoryService(repo), repository=repo, backend="supabase"
            )
        except SupabaseConfigurationError as exc:
            reason = str(exc)
        except Exception as exc:  # noqa: BLE001 - any Supabase failure degrades safely
            reason = f"supabase indisponível · {type(exc).__name__}: {exc}"
    except ImportError as exc:  # pragma: no cover - supabase_adapter always imports
        reason = str(exc)

    service = MemoryService(repo)
    return MemoryStack(
        service=service, repository=repo, backend="inmemory", fallback_reason=reason
    )
