from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from core.execution_result import ExecutionResult


_CONTRACT_KEYS = {
    "action",
    "ok",
    "delivered",
    "verified",
    "evidence",
    "error",
    "risk",
    "requires_approval",
    "message",
    "correlation_id",
    "can_claim_success",
}
_FAILURE_TOKENS = (
    "failed",
    "error",
    "timeout",
    "timed out",
    "not found",
    "could not",
    "unknown action",
    "permission denied",
)


# -.-.-.-
def _decode_payload(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


# -.-.-.-
def _extract_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    explicit = payload.get("evidence")
    if isinstance(explicit, Mapping):
        evidence.update(explicit)

    for key, value in payload.items():
        if key not in _CONTRACT_KEYS:
            evidence[key] = value
    return evidence


# -.-.-.-
def verify_tool_result(
    value: Any,
    *,
    action: str,
    risk: str = "safe",
) -> ExecutionResult:
    """Convert a raw tool result without inventing postconditions.

    Explicit structured `verified=true` is honoured. Legacy strings and mappings
    without an explicit verification signal remain unverified even if they say
    "done" or return `ok=true`.
    """
    if isinstance(value, ExecutionResult):
        return value

    payload = _decode_payload(value)
    if payload is not None:
        verified = payload.get("verified") is True
        delivered = payload.get("delivered") is True or verified
        ok = payload.get("ok") is True or verified
        error = payload.get("error")
        requires_approval = payload.get("requires_approval") is True
        result_action = str(payload.get("action") or action or "unknown")
        result_risk = str(payload.get("risk") or risk or "safe")

        if error is not None:
            ok = False
            verified = False

        return ExecutionResult(
            action=result_action,
            ok=ok,
            delivered=delivered,
            verified=verified,
            evidence=_extract_evidence(payload),
            error=str(error) if error is not None else None,
            risk=result_risk,
            requires_approval=requires_approval,
            message=str(payload.get("message") or ""),
            correlation_id=(
                str(payload.get("correlation_id"))
                if payload.get("correlation_id") is not None
                else None
            ),
        )

    text = str(value or "").strip()
    lowered = text.casefold()
    if not text:
        return ExecutionResult.failure(action, "Tool returned no result.", risk=risk)
    if any(token in lowered for token in _FAILURE_TOKENS):
        return ExecutionResult.failure(action, text[:500], delivered=False, risk=risk)

    return ExecutionResult.unverified_delivery(
        action,
        evidence={"legacy_result": text[:500]},
        message="The command returned a legacy result but its effect was not verified.",
        risk=risk,
    )


# -.-.-.-
def claim_safe_message(result: ExecutionResult, *, success_message: str = "Concluído.") -> str:
    """Return user-facing wording that cannot turn unverified delivery into success."""
    if result.can_claim_success:
        return result.message or success_message
    if result.requires_approval:
        return result.message or result.error or "Esta acção requer aprovação antes de continuar."
    if result.error:
        return result.error
    if result.delivered:
        return result.message or "A acção foi enviada, mas ainda não consegui verificar o efeito."
    return result.message or "Não consegui confirmar a execução desta acção."
