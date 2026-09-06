"""Natural memory command classification (ANT-276 D19).

Deterministic, fail-closed classification of explicit pt-PT memory
commands into an intent + required approval. Ordinary sentences return
``None`` and stay in the normal conversation flow. NOTHING here mutates
memory: the caller feeds the classified intent to ``MemoryService`` and
honors ``requires_approval`` through the canonical approval flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

INTENTS = (
    "learn_fact",        # "Aprende que..."
    "learn_procedure",   # "Aprende como..." / "Aprende a..."
    "preference",        # "Prefiro..."
    "correct",           # "Corrige..."
    "forget",            # "Esquece..."
    "list_knowledge",    # "Mostra o que sabes..."
    "explain_source",    # "De onde aprendeste isto?"
)

# D18/D19: anything that mutates memory requires approval first.
MUTATING_INTENTS = frozenset(
    {"learn_fact", "learn_procedure", "preference", "correct", "forget"}
)

# Put longer/specific markers before their prefixes. Matching also checks a
# boundary, so e.g. "corrigeste" is not mistaken for the command "corrige".
_MARKERS: tuple[tuple[str, str], ...] = (
    ("mostra o que sabes", "list_knowledge"),
    ("o que sabes sobre", "list_knowledge"),
    ("de onde aprendeste", "explain_source"),
    ("onde aprendeste", "explain_source"),
    ("aprende como", "learn_procedure"),
    ("aprende que", "learn_fact"),
    ("aprende a", "learn_procedure"),
    ("prefiro ouvir", "preference"),
    ("prefiro", "preference"),
    ("esquece que", "forget"),
    ("esquece", "forget"),
    ("corrige", "correct"),
)

_BOUNDARY_CHARS = frozenset(" \t\r\n:;,.!?—-()[]{}")


@dataclass(frozen=True)
class MemoryCommand:
    intent: str
    payload: str
    requires_approval: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "payload": self.payload,
            "requires_approval": self.requires_approval,
        }


# -.-.-.-
def _matches_marker(normalized: str, marker: str) -> bool:
    if not normalized.startswith(marker):
        return False
    if len(normalized) == len(marker):
        return True
    return normalized[len(marker)] in _BOUNDARY_CHARS


# -.-.-.-
def classify_memory_command(text: str | None) -> MemoryCommand | None:
    """Classify an explicit memory utterance without changing its payload.

    Matching is case-insensitive, but the payload is sliced from the
    original user text so names, acronyms and project identifiers retain
    their spelling. Mutating intents always require approval.
    """
    original = str(text or "").strip()
    if not original:
        return None
    normalized = original.casefold()

    for marker, intent in _MARKERS:
        if not _matches_marker(normalized, marker):
            continue
        payload = original[len(marker):].strip(" \t\r\n:;,.!?")
        if intent in MUTATING_INTENTS and not payload:
            # A mutation with no target/content is too ambiguous to hand to
            # a memory service; keep it in normal conversation instead.
            return None
        return MemoryCommand(
            intent=intent,
            payload=payload,
            requires_approval=intent in MUTATING_INTENTS,
        )
    return None
