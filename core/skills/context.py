"""SkillContext (ANT-277 E4): minimal, isolated, explicit capabilities.

A skill never sees the UI, the DB client, global keys or global mutable
state. Secrets are injected explicitly per-skill and are never part of
repr/serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class SkillContext:
    working_dir: Path                      # isolated per run
    permissions: frozenset[str]            # granted subset, never the full set
    secrets: frozenset[tuple[str, str]] = field(default_factory=frozenset)  # explicit injection only
    log: Callable[[str], None] = print     # redaction is the runtime's job

    def __post_init__(self) -> None:
        object.__setattr__(self, "working_dir", Path(self.working_dir))

    # -.-.-.-
    def secret(self, name: str) -> str:
        """Explicit secret lookup; names are declared, never enumerated."""
        for key, value in self.secrets:
            if key == name:
                return value
        raise KeyError(f"secret not granted: {name}")

    # -.-.-.-
    def redacted_dict(self) -> dict[str, object]:
        """Serializable view without ever exposing secret values."""
        return {
            "working_dir": str(self.working_dir),
            "permissions": sorted(self.permissions),
            "secrets_granted": sorted(name for name, _ in self.secrets),
        }
