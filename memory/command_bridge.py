"""Runtime wiring for memory commands and bounded habit suggestions.

``MemoryCommandBridge`` connects the deterministic memory-command
classifier to ``MemoryService`` without bypassing lifecycle rules:

- read-only intents query ACTIVE memory only;
- learn/preference/correct create PROPOSED records and never auto-activate;
- forget resolves a target but does NOT archive/delete until an approval
  flow explicitly performs that mutation;
- procedure learning produces procedural memory, not a semantic fact;
- habit observations may produce suggestions, never execution.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable

from memory.domain import SourceKind
from memory.natural_commands import classify_memory_command
from memory.service import MemoryService
from tasks.proactivity import Observation, habit_stage, suggestion_allowed


class MemoryCommandBridge:
    def __init__(
        self,
        service: MemoryService,
        *,
        owner_id: str = "local",
        log: Callable[[str], None] = lambda text: None,
        max_observations: int = 500,
        duplicate_window_seconds: float = 1.0,
    ):
        self._service = service
        self._owner_id = owner_id
        self._log = log
        self._observations: deque[Observation] = deque(maxlen=max_observations)
        self._notified_stages: set[tuple[str, str]] = set()
        self._duplicate_window_seconds = max(0.0, float(duplicate_window_seconds))
        self._lock = threading.Lock()

    # -.-.-.-
    @staticmethod
    def _search_text(payload: str) -> str | None:
        value = str(payload or "").strip()
        lowered = value.casefold()
        if lowered.startswith("sobre "):
            value = value[6:].strip()
            lowered = value.casefold()
        if lowered in {"", "isto", "isso", "isto?", "isso?"}:
            return None
        return value

    # -.-.-.-
    def _retrieve_one(self, payload: str):
        return self._service.retrieve(
            owner_id=self._owner_id,
            text=self._search_text(payload),
            top_k=1,
        )

    # -.-.-.-
    def handle(self, text: str) -> dict[str, Any] | None:
        """Handle one explicit memory utterance, or return ``None``.

        No mutating command becomes ACTIVE here. The result explicitly
        indicates when human approval is still required.
        """
        command = classify_memory_command(text)
        if command is None:
            return None

        service = self._service

        if command.intent == "learn_fact":
            proposal = service.propose(
                owner_id=self._owner_id,
                type_="semantic",
                title=command.payload[:80] or "Conhecimento",
                content=command.payload,
                source_kind=SourceKind.USER,
            )
            return {
                "intent": command.intent,
                "spoken": "Guardei isso como proposta; precisa da tua aprovação para ficar activo.",
                "proposal_id": proposal.id,
                "requires_approval": True,
            }

        if command.intent == "learn_procedure":
            proposal = service.propose(
                owner_id=self._owner_id,
                type_="procedural",
                title=command.payload[:80] or "Procedimento",
                content=command.payload,
                source_kind=SourceKind.USER,
            )
            return {
                "intent": command.intent,
                "spoken": "Guardei o procedimento como proposta; precisa da tua aprovação antes de ficar activo.",
                "proposal_id": proposal.id,
                "requires_approval": True,
            }

        if command.intent == "preference":
            proposal = service.propose(
                owner_id=self._owner_id,
                type_="semantic",
                title=command.payload[:80] or "Preferência",
                content=command.payload,
                source_kind=SourceKind.USER,
            )
            return {
                "intent": command.intent,
                "spoken": "Guardei a preferência como proposta; precisa da tua aprovação.",
                "proposal_id": proposal.id,
                "requires_approval": True,
            }

        if command.intent == "correct":
            matches = self._retrieve_one(command.payload)
            if not matches:
                return {
                    "intent": command.intent,
                    "spoken": "Não encontrei a memória a corrigir.",
                    "requires_approval": False,
                }
            proposal = service.supersede(
                matches[0].record.id,
                owner_id=self._owner_id,
                content=command.payload,
            )
            return {
                "intent": command.intent,
                "spoken": "A correcção ficou como proposta; precisa da tua aprovação.",
                "proposal_id": proposal.id,
                "target_id": matches[0].record.id,
                "requires_approval": True,
            }

        if command.intent == "forget":
            matches = self._retrieve_one(command.payload)
            if not matches:
                return {
                    "intent": command.intent,
                    "spoken": "Não encontrei essa memória.",
                    "requires_approval": False,
                }
            # Forget/archive is itself a mutation. The classifier explicitly
            # marks it approval-required, so the bridge only identifies the
            # target. A canonical approval flow must perform the mutation.
            return {
                "intent": command.intent,
                "spoken": "Encontrei a memória. Preciso da tua aprovação antes de a arquivar ou apagar.",
                "target_id": matches[0].record.id,
                "requires_approval": True,
                "pending_action": "archive_memory",
            }

        if command.intent == "list_knowledge":
            hits = service.retrieve(
                owner_id=self._owner_id,
                text=self._search_text(command.payload),
                top_k=5,
            )
            items = [hit.record.title for hit in hits]
            spoken = "O que sei: " + "; ".join(items) if items else "Não encontrei memória activa sobre isso."
            return {
                "intent": command.intent,
                "spoken": spoken,
                "requires_approval": False,
            }

        if command.intent == "explain_source":
            hits = self._retrieve_one(command.payload)
            if not hits:
                return {
                    "intent": command.intent,
                    "spoken": "Não encontrei essa memória activa.",
                    "requires_approval": False,
                }
            chain = service.explain_source(
                hits[0].record.id,
                owner_id=self._owner_id,
            )
            source = "desconhecida"
            if chain.get("chain"):
                source = str(chain["chain"][0].get("source_kind") or source)
            return {
                "intent": command.intent,
                "spoken": f"Origem: {source}.",
                "memory_id": hits[0].record.id,
                "requires_approval": False,
            }

        return {
            "intent": command.intent,
            "spoken": "Não sei lidar com esse pedido de memória.",
            "requires_approval": False,
        }

    # -.-.-.-
    def observe(self, signature: str) -> str | None:
        """Feed the habit ladder and return a suggestion on stage transition.

        The tiny duplicate window only suppresses duplicate instrumentation
        of the same event; it is not a claim that several rapid actions form
        a durable habit.
        """
        normalized = str(signature or "").strip()
        if not normalized:
            return None
        now = time.time()
        with self._lock:
            if self._observations:
                previous = self._observations[-1]
                if (
                    previous.signature == normalized
                    and now - previous.at_epoch <= self._duplicate_window_seconds
                ):
                    return None

            self._observations.append(Observation(normalized, now))
            stage = habit_stage(list(self._observations), signature=normalized)
            notification_key = (normalized, stage)
            if (
                not suggestion_allowed(stage)
                or notification_key in self._notified_stages
            ):
                return None
            self._notified_stages.add(notification_key)
            return (
                f"Notei um padrão: {normalized}. Queres criar uma rotina? "
                "(sugestão — nada corre automaticamente)"
            )
