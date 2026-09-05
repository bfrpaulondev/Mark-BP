"""Voice feedback mapping for verified execution results (ANT-271).

Pure Python layer between the runtime's ``ExecutionResult`` contract and
pt-PT voice phrases. The verifier is the single source of truth:

- no success speech before verified success (``can_claim_success``);
- delivered-but-unverified actions say so explicitly;
- cancellations are never reported as failures;
- approval requests never approve, create grants or simulate confirmation;
- untrusted mappings/flags never become a trusted success result here.

This module never redefines ``ExecutionResult`` semantics and carries no
private content: phrases are fixed strings and evidence is never read.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.execution_result import ExecutionResult
from core.local_command_router import LocalCommandResult


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
    """A single voice-ready utterance derived from a trusted runtime result."""

    category: str
    phrase_pt: str
    announce: bool = True

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown voice feedback category: {self.category}")


# -.-.-.-
def execution_result_to_voice_feedback(result: object) -> VoiceFeedback:
    """Map a trusted ``ExecutionResult`` into honest voice feedback.

    Fail-closed: this boundary deliberately does not normalize arbitrary
    mappings. Provider/model/tool dictionaries are untrusted data and cannot
    prove verification by setting boolean flags. Callers must supply the
    canonical runtime ``ExecutionResult`` produced by the execution/verifier
    boundary; every other input becomes a failure utterance.
    """
    if not isinstance(result, ExecutionResult):
        return VoiceFeedback("failure", "Não consegui concluir.")

    if result.requires_approval:
        return VoiceFeedback(
            "waiting_approval",
            "Preciso da tua aprovação para continuar.",
        )

    if result.can_claim_success:
        return VoiceFeedback("verified_success", "Concluído.")

    if result.ok and result.delivered and not result.verified:
        return VoiceFeedback(
            "unverified_delivery",
            "Executei a acção, mas não consegui confirmar o resultado.",
        )

    return VoiceFeedback("failure", "Não consegui concluir.")


# -.-.-.-
def local_command_feedback(
    result: LocalCommandResult,
    verification: ExecutionResult | None = None,
) -> VoiceFeedback:
    """Map a trusted deterministic fast-path outcome into voice feedback.

    ``LocalCommandResult`` is produced by our own router (trusted app
    code), so the isinstance boundary keeps the same policy as
    ``execution_result_to_voice_feedback``: only a verified outcome may
    carry a success utterance, and an explicit verifier result wins when
    provided.
    """
    if verification is not None:
        return execution_result_to_voice_feedback(verification)
    if not isinstance(result, LocalCommandResult):
        return VoiceFeedback("failure", "Não consegui concluir.")

    message = str(result.message or "").strip()
    if not result.handled:
        return VoiceFeedback("failure", message or "Não consegui concluir.")
    if result.verified:
        return VoiceFeedback("verified_success", message or "Concluído.")
    return VoiceFeedback(
        "unverified_delivery",
        message or "Executei a acção, mas não consegui confirmar o resultado.",
    )


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
