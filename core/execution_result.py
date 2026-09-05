from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ExecutionResult:
    """Canonical runtime result for actions that may cause or observe side effects."""

    action: str
    ok: bool
    delivered: bool
    verified: bool
    evidence: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    risk: str = "safe"
    requires_approval: bool = False
    message: str = ""
    correlation_id: str | None = None

    @property
    def can_claim_success(self) -> bool:
        """Only verified successful delivery may be described as completed."""
        return bool(self.ok and self.delivered and self.verified and not self.error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "ok": self.ok,
            "delivered": self.delivered,
            "verified": self.verified,
            "evidence": dict(self.evidence),
            "error": self.error,
            "risk": self.risk,
            "requires_approval": self.requires_approval,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "can_claim_success": self.can_claim_success,
        }

    # -.-.-.-
    @classmethod
    def verified_success(
        cls,
        action: str,
        *,
        evidence: Mapping[str, Any] | None = None,
        message: str = "",
        risk: str = "safe",
        correlation_id: str | None = None,
    ) -> "ExecutionResult":
        return cls(
            action=action,
            ok=True,
            delivered=True,
            verified=True,
            evidence=evidence or {},
            risk=risk,
            message=message,
            correlation_id=correlation_id,
        )

    # -.-.-.-
    @classmethod
    def unverified_delivery(
        cls,
        action: str,
        *,
        evidence: Mapping[str, Any] | None = None,
        message: str = "",
        risk: str = "safe",
        correlation_id: str | None = None,
    ) -> "ExecutionResult":
        return cls(
            action=action,
            ok=True,
            delivered=True,
            verified=False,
            evidence=evidence or {},
            risk=risk,
            message=message,
            correlation_id=correlation_id,
        )

    # -.-.-.-
    @classmethod
    def failure(
        cls,
        action: str,
        error: str,
        *,
        delivered: bool = False,
        evidence: Mapping[str, Any] | None = None,
        risk: str = "safe",
        requires_approval: bool = False,
        correlation_id: str | None = None,
    ) -> "ExecutionResult":
        return cls(
            action=action,
            ok=False,
            delivered=delivered,
            verified=False,
            evidence=evidence or {},
            error=str(error),
            risk=risk,
            requires_approval=requires_approval,
            correlation_id=correlation_id,
        )


# -.-.-.-
def normalize_execution_result(value: ExecutionResult | Mapping[str, Any], *, action: str = "") -> ExecutionResult:
    """Normalize structured tool results while refusing to infer verification."""
    if isinstance(value, ExecutionResult):
        return value

    payload = dict(value)
    return ExecutionResult(
        action=str(payload.get("action") or action or "unknown"),
        ok=bool(payload.get("ok", False)),
        delivered=bool(payload.get("delivered", False)),
        verified=bool(payload.get("verified", False)),
        evidence=payload.get("evidence") if isinstance(payload.get("evidence"), Mapping) else {},
        error=str(payload["error"]) if payload.get("error") is not None else None,
        risk=str(payload.get("risk") or "safe"),
        requires_approval=bool(payload.get("requires_approval", False)),
        message=str(payload.get("message") or ""),
        correlation_id=(
            str(payload.get("correlation_id"))
            if payload.get("correlation_id") is not None
            else None
        ),
    )
