"""Voice feedback mapping for verification results (ANT-271).

Pure Python layer between the runtime's ``ExecutionResult`` contract and
pt-PT voice phrases. The verifier is the single source of truth:

- NO SUCCESS SPEECH BEFORE VERIFIED SUCCESS (``can_claim_success``);
- delivered-but-unverified actions must say so explicitly;
- cancellations are never reported as failures;
- approval requests never approve, never create grants and never
  simulate confirmation — they only ask.

This module never redefines ``ExecutionResult`` semantics and carries no
private content: phrases are fixed strings, evidence is never read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.execution_result import ExecutionResult, normalize_execution_result


CATEGORIES = (
    "verified_success",
    "unverified_delivery",
    "failure",
    "waiting_approval",
    "cancelled",
    "recovery",
)


@dataclass(frozen=True)
class VoiceFeedback:
    """A single voice-ready utterance derived from a verified outcome."""

    category: str
    phrase_pt: str
    announce: bool = True

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown voice feedback category: {self.category}")


# -.-.-.-
def execution_result_to_voice_feedback(result: ExecutionResult | dict) -> VoiceFeedback:
    """Map a (possibly untrusted) result into honest voice feedback.

    Fail-closed: anything that cannot prove verified success is never
    announced as success; unknown or malformed inputs fall through to the
    failure phrase.
    """
    normalized: ExecutionResult
    if isinstance(result, ExecutionResult):
        normalized = result
    elif isinstance(result, Mapping):
        normalized = normalize_execution_result(result)
    else:
        # Non-mapping garbage (None, strings, numbers) can never prove
        # success — fail closed to the failure phrase.
        return VoiceFeedback("failure", "Não consegui concluir.")

    if normalized.requires_approval:
        return VoiceFeedback(
            "waiting_approval",
            "Preciso da tua aprovação para continuar.",
        )

    if normalized.can_claim_success:
        return VoiceFeedback("verified_success", "Concluído.")

    if normalized.ok and normalized.delivered and not normalized.verified:
        return VoiceFeedback(
            "unverified_delivery",
            "Executei a acção, mas não consegui confirmar o resultado.",
        )

    return VoiceFeedback("failure", "Não consegui concluir.")


# -.-.-.-
def cancelled_feedback() -> VoiceFeedback:
    """Cancellation is its own category — never reported as a failure."""
    return VoiceFeedback("cancelled", "Cancelado.")


# -.-.-.-
def recovery_feedback() -> VoiceFeedback:
    """Short, calm notice that a bounded retry/recovery is starting."""
    return VoiceFeedback(
        "recovery",
        "Não encontrei o esperado. Vou tentar novamente.",
    )
