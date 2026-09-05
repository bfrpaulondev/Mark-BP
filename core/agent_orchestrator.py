from __future__ import annotations

import inspect
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from core.execution_result import ExecutionResult


class AgentStage(str, Enum):
    ROUTE = "route"
    POLICY = "policy"
    OBSERVE = "observe"
    EXECUTE = "execute"
    VERIFY = "verify"
    RECOVER = "recover"
    FINISH = "finish"
    FAILED = "failed"


@dataclass(frozen=True)
class OrchestrationEvent:
    correlation_id: str
    stage: AgentStage
    tool_name: str
    timestamp: float
    detail: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "stage": self.stage.value,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
            "detail": self.detail,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ToolOrchestrationOutcome:
    correlation_id: str
    tool_name: str
    raw_response: Any
    response_payload: dict[str, Any]
    execution: ExecutionResult | None
    events: tuple[OrchestrationEvent, ...]
    duration_ms: int

    @property
    def can_claim_success(self) -> bool:
        if self.execution is None:
            return True
        return bool(self.execution.can_claim_success)

    def trace(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]


class AgentOrchestrator:
    """Incremental orchestration shell around the existing Antonella tool runtime.

    This class deliberately does not implement routing, authorization policy or provider
    selection yet. Those responsibilities remain legacy/pass-through until ANT-260–263.
    Its job in ANT-259 is to own the execution lifecycle and make the boundaries explicit:

    route -> policy boundary -> observe -> execute -> observe -> verify -> finish

    The injected callbacks keep this module provider-neutral and preserve the current
    runtime while later tasks replace each boundary independently.
    """

    def __init__(
        self,
        *,
        requires_postcondition: Callable[[str, Mapping[str, Any] | None], bool],
        capture_postcondition_state: Callable[[str, Mapping[str, Any] | None], Mapping[str, Any]],
        verify_postcondition: Callable[..., ExecutionResult],
        event_sink: Callable[[OrchestrationEvent], Any] | None = None,
    ) -> None:
        self._requires_postcondition = requires_postcondition
        self._capture_postcondition_state = capture_postcondition_state
        self._verify_postcondition = verify_postcondition
        self._event_sink = event_sink

    # -.-.-.-
    async def run_tool(
        self,
        *,
        tool_name: str,
        args: Mapping[str, Any] | None,
        executor: Callable[[], Any | Awaitable[Any]],
    ) -> ToolOrchestrationOutcome:
        name = str(tool_name or "").strip()
        params = dict(args or {})
        correlation_id = uuid.uuid4().hex[:16]
        started = time.monotonic()
        events: list[OrchestrationEvent] = []

        self._emit(
            events,
            correlation_id,
            AgentStage.ROUTE,
            name,
            detail="legacy_tool_route",
            metadata={"argument_names": sorted(str(key) for key in params)},
        )

        # ANT-261 will replace this explicit boundary with the central Policy Engine.
        # No new authorization decision is made by ANT-259; legacy behaviour is preserved.
        self._emit(
            events,
            correlation_id,
            AgentStage.POLICY,
            name,
            detail="legacy_policy_passthrough",
            metadata={"central_policy_active": False},
        )

        needs_postcondition = bool(self._requires_postcondition(name, params))
        before_state: Mapping[str, Any] | None = None
        if needs_postcondition:
            self._emit(
                events,
                correlation_id,
                AgentStage.OBSERVE,
                name,
                detail="capture_precondition_state",
                metadata={"phase": "before"},
            )
            before_state = self._capture_postcondition_state(name, params)

        self._emit(
            events,
            correlation_id,
            AgentStage.EXECUTE,
            name,
            detail="dispatch_existing_runtime_tool",
            metadata={"requires_postcondition": needs_postcondition},
        )

        try:
            raw_response = executor()
            if inspect.isawaitable(raw_response):
                raw_response = await raw_response
        except Exception as exc:
            self._emit(
                events,
                correlation_id,
                AgentStage.FAILED,
                name,
                detail="executor_exception",
                metadata={"error_type": type(exc).__name__},
            )
            raise

        payload = self._extract_payload(raw_response)
        execution: ExecutionResult | None = None

        if needs_postcondition:
            self._emit(
                events,
                correlation_id,
                AgentStage.OBSERVE,
                name,
                detail="capture_postcondition_state",
                metadata={"phase": "after"},
            )
            self._emit(
                events,
                correlation_id,
                AgentStage.VERIFY,
                name,
                detail="verify_effect",
            )
            execution = self._verify_postcondition(
                name,
                params,
                payload.get("result"),
                before_state=before_state,
            )
            if not execution.correlation_id:
                execution = replace(execution, correlation_id=correlation_id)
            payload["execution"] = execution.to_dict()
            if not execution.can_claim_success:
                payload["verification_note"] = (
                    "Do not claim this effect succeeded unless execution.can_claim_success is true."
                )

        duration_ms = max(0, round((time.monotonic() - started) * 1000))
        self._emit(
            events,
            correlation_id,
            AgentStage.FINISH,
            name,
            detail="tool_lifecycle_complete",
            metadata={
                "duration_ms": duration_ms,
                "verified": execution.verified if execution is not None else None,
                "can_claim_success": execution.can_claim_success if execution is not None else None,
            },
        )

        return ToolOrchestrationOutcome(
            correlation_id=correlation_id,
            tool_name=name,
            raw_response=raw_response,
            response_payload=payload,
            execution=execution,
            events=tuple(events),
            duration_ms=duration_ms,
        )

    # -.-.-.-
    def _extract_payload(self, response: Any) -> dict[str, Any]:
        if isinstance(response, Mapping):
            return dict(response)
        try:
            payload = getattr(response, "response", None)
            if isinstance(payload, Mapping):
                return dict(payload)
        except Exception:
            pass
        return {"result": response}

    # -.-.-.-
    def _emit(
        self,
        events: list[OrchestrationEvent],
        correlation_id: str,
        stage: AgentStage,
        tool_name: str,
        *,
        detail: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        event = OrchestrationEvent(
            correlation_id=correlation_id,
            stage=stage,
            tool_name=tool_name,
            timestamp=time.time(),
            detail=detail,
            metadata=dict(metadata or {}),
        )
        events.append(event)
        if self._event_sink is None:
            return
        try:
            self._event_sink(event)
        except Exception:
            # Observability must never break task execution.
            pass
