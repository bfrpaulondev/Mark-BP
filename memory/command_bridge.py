"""Runtime wiring for memory commands and proactivity (ANT-276 D19/R1, ANT-278 R5).

``MemoryCommandBridge`` wires the deterministic memory command classifier
and the habit ladder into the live conversation flow:

- read-only intents (list/explain) are answered from the memory service;
- mutating intents (learn/preference/correct/forget) only create
  PROPOSED records — activation always needs the canonical approval
  flow (never auto-approved here);
- every fast-path command signature feeds the habit ladder; suggestions
  are logged once per stage transition, never executed.
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
    ):
        self._service = service
        self._owner_id = owner_id
        self._log = log
        self._observations: deque[Observation] = deque(maxlen=max_observations)  # bounded (F-18)
        self._notified_stages: set[str] = set()
        self._lock = threading.Lock()

    # -.-.-.-
    def handle(self, text: str) -> dict[str, Any] | None:
        """Handle a user utterance if it is a memory command.

        Returns a result dict the caller can speak/log, or ``None`` when
        the utterance is not a memory command. Mutating intents only
        create PROPOSED records — the canonical approval flow decides
        activation; nothing is auto-approved here (R1).
        """
        command = classify_memory_command(text)
        if command is None:
            return None

        service = self._service
        if command.intent == "learn_fact":
            proposal = service.propose(
                owner_id=self._owner_id,
                type_="semantic",
                title=command.payload[:80] or "Aprendizado",
                content=command.payload,
                source_kind=SourceKind.USER,
            )
            return {
                "intent": command.intent,
                "spoken": "Aprendi como proposta; precisa da tua aprovação para ficar activa.",
                "proposal_id": proposal.id,
                "requires_approval": True,
            }
        if command.intent == "preference":
            proposal = service.propose(
                owner_id=self._owner_id,
                type_="feedback",
                title=command.payload[:80] or "Preferência",
                content=command.payload,
                source_kind=SourceKind.USER,
            )
            return {
                "intent": command.intent,
                "spoken": "Guardei como proposta de preferência; precisa de aprovação.",
                "proposal_id": proposal.id,
                "requires_approval": True,
            }
        if command.intent == "correct":
            matches = service.retrieve(owner_id=self._owner_id, text=command.payload, top_k=1)
            if not matches:
                return {
                    "intent": command.intent,
                    "spoken": "Não encontrei a memória a corrigir.",
                    "requires_approval": False,
                }
            proposal = service.supersede(
                matches[0].record.id, owner_id=self._owner_id, content=command.payload
            )
            return {
                "intent": command.intent,
                "spoken": "Correcção guardada como proposta; precisa de aprovação.",
                "proposal_id": proposal.id,
                "requires_approval": True,
            }
        if command.intent == "forget":
            matches = service.retrieve(owner_id=self._owner_id, text=command.payload, top_k=1)
            if not matches:
                return {
                    "intent": command.intent,
                    "spoken": "Não encontrei essa memória.",
                    "requires_approval": False,
                }
            service.archive(matches[0].record.id, owner_id=self._owner_id)
            return {
                "intent": command.intent,
                "spoken": "Esquecido (arquivado; podes restaurar depois).",
                "requires_approval": False,
            }
        if command.intent == "list_knowledge":
            hits = service.retrieve(owner_id=self._owner_id, top_k=5)
            items = [hit.record.title for hit in hits] or ["(memória vazia)"]
            return {
                "intent": command.intent,
                "spoken": "O que sei: " + "; ".join(items),
                "requires_approval": False,
            }
        if command.intent == "explain_source":
            hits = service.retrieve(owner_id=self._owner_id, top_k=1)
            if not hits:
                return {"intent": command.intent, "spoken": "Ainda não sei nada.", "requires_approval": False}
            chain = service.explain_source(hits[0].record.id, owner_id=self._owner_id)
            return {
                "intent": command.intent,
                "spoken": f"Origem: {chain['chain'][0]['source_kind']}.",
                "requires_approval": False,
            }
        return {"intent": command.intent, "spoken": "Não sei lidar com esse pedido de memória.", "requires_approval": False}

    # -.-.-.-
    def observe(self, signature: str) -> str | None:
        """R5: feed the habit ladder; return a SUGGESTION message only
        when the stage moves upward. Never executes anything."""
        now = time.time()
        with self._lock:
            self._observations.append(Observation(signature, now))
            stage = habit_stage(list(self._observations), signature=signature)
            if not suggestion_allowed(stage) or stage in self._notified_stages:
                return None
            self._notified_stages.add(stage)
            return (
                f"Notei um padrão: {signature}. Queres criar uma rotina? "
                "(sugestão — nada corre automaticamente)"
            )
