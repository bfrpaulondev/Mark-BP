"""SkillResult (ANT-277 E5): machine-readable, ExecutionResult-compatible."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.execution_result import ExecutionResult


@dataclass(frozen=True)
class SkillResult:
    """Skill outcome. ``verified`` stays False unless a postcondition
    actually proved the effect — running without crashing is delivery,
    not verification."""

    skill_slug: str
    ok: bool
    delivered: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    verified: bool = False
    risk: str = "low"
    duration_ms: int | None = None

    # -.-.-.-
    @property
    def can_claim_success(self) -> bool:
        return bool(self.ok and self.delivered and self.verified and not self.error)

    # -.-.-.-
    def to_execution_result(self) -> ExecutionResult:
        """Map INTO the canonical contract — semantics are consumed, not redefined."""
        return ExecutionResult(
            action=f"skill.{self.skill_slug}",
            ok=self.ok,
            delivered=self.delivered,
            verified=self.verified,
            evidence={"output_keys": sorted(self.output), "duration_ms": self.duration_ms},
            error=self.error,
            risk=self.risk,
        )
