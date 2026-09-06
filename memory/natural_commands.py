"""Natural memory command classification (ANT-276 D19).

Deterministic, fail-closed classification of pt-PT memory commands into
an intent + required approval. Only explicit markers classify as memory
commands — an ordinary sentence returns ``None`` and stays with the
normal conversation flow. NOTHING here mutates memory: the caller feeds
the classified intent to ``MemoryService`` and honors
``requires_approval`` through the canonical approval flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

INTENTS = (
    "learn_fact",       # "Aprende que..."
    "preference",       # "Prefiro..."
    "correct",          # "Corrige..."
    "forget",           # "Esquece..."
    "list_knowledge",   # "Mostra o que sabes..."
    "explain_source",   # "De onde aprendeste isto?"
)

# D18/D19: anything that mutates memory requires approval first.
MUTATING_INTENTS = frozenset({"learn_fact", "preference", "correct", "forget"})

_MARKERS: tuple[tuple[str, str], ...] = (
    ("aprende que", "learn_fact"),
    ("aprende como", "learn_fact"),
    ("aprende a", "learn_fact"),
    ("prefiro", "preference"),
    ("prefiro ouvir", "preference"),
    ("corrige", "correct"),
    ("esquece", "forget"),
    ("esquece que", "forget"),
    ("mostra o que sabes", "list_knowledge"),
    ("o que sabes sobre", "list_knowledge"),
    ("de onde aprendeste", "explain_source"),
    ("onde aprendeste", "explain_source"),
)


@dataclass(frozen=True)
class MemoryCommand:
    intent: str
    payload: str          # the user text after the marker — never persisted raw
    requires_approval: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "payload": self.payload,
            "requires_approval": self.requires_approval,
        }


def classify_memory_command(text: str) -> MemoryCommand | None:
    """Classify a user utterance; ``None`` when it is not a memory command.

    Fail-closed: mutating intents always carry ``requires_approval=True``;
    read-only intents (list/explain) do not.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return None
    for marker, intent in _MARKERS:
        if lowered.startswith(marker):
            payload = lowered[len(marker):].strip(" :.")
            return MemoryCommand(
                intent=intent,
                payload=payload,
                requires_approval=intent in MUTATING_INTENTS,
            )
    return None
