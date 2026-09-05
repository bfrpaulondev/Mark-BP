from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from core.execution_engine import ExecutionEngine
from core.execution_result import ExecutionResult
from core.policy_engine import PolicyDecision, PolicyEffect, PolicyEngine
from core.tool_router import ToolRouter


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
    route_tier: str = "legacy"
    policy_effect: str = "write"
    policy_rule: str = ""

    @property
    def can_claim_success(self) -> bool:
        if self.execution is None:
            return True
        return bool(self.execution.can_claim_success)

    def trace(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]


class AgentOrchestrator:
    """Provider-neutral execution lifecycle for Antonella tool calls.

    ANT-259 established the lifecycle and ANT-260 separated routing/dispatch. ANT-261
    inserts a deterministic Policy Engine before any observation or side effect:

    route -> policy -> observe -> execute -> observe -> verify -> finish

    The policy gate never trusts model-supplied approval flags. Action-bound human approval
    tokens are intentionally deferred to ANT-262; until then approval-required operations
    stop safely before execution.
    """

    def __init__(
        self,
        *,
        requires_postcondition: Callable[[str, Mapping[str, Any] | None], bool],
        capture_postcondition_state: Callable[[str, Mapping[str, Any] | None], Mapping[str, Any]],
        verify_postcondition: Callable[..., ExecutionResult],
        event_sink: Callable[[OrchestrationEvent], Any] | None = None,
        tool_router: ToolRouter | None = None,
        execution_engine: ExecutionEngine | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self._requires_postcondition = requires_postcondition
        self._capture_postcondition_state = capture_postcondition_state
        self._verify_postcondition = verify_postcondition
        self._event_sink = event_sink
        self._tool_router = tool_router or ToolRouter()
        self._execution_engine = execution_engine or ExecutionEngine()
        self._policy_engine = policy_engine or PolicyEngine()

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
        route = self._tool_router.route(name, params)

        self._emit(
            events,
            correlation_id,
            AgentStage.ROUTE,
            name,
            detail="deterministic_tool_route",
            metadata={
                "argument_names": sorted(str(key) for key in params),
                "route_tier": route.tier.value,
                "route_reason": route.reason,
            },
        )

        decision = self._policy_engine.evaluate(name, params)
        self._emit(
            events,
            correlation_id,
            AgentStage.POLICY,
            name,
            detail="central_policy_decision",
            metadata=decision.safe_metadata(),
        )

        if decision.blocks_execution:
            return self._policy_stopped_outcome(
                name=name,
                route_tier=route.tier.value,
                decision=decision,
                correlation_id=correlation_id,
                started=started,
                events=events,
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
            detail="dispatch_execution_engine",
            metadata={
                "requires_postcondition": needs_postcondition,
                "route_tier": route.tier.value,
                "policy_effect": decision.effect.value,
            },
        )

        try:
            dispatch = await self._execution_engine.execute(route, executor)
            raw_response = dispatch.raw_response
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

        payload["policy"] = decision.safe_metadata()
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
                "policy_effect": decision.effect.value,
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
            route_tier=route.tier.value,
            policy_effect=decision.effect.value,
            policy_rule=decision.rule_id,
        )

    # -.-.-.-
    def _policy_stopped_outcome(
        self,
        *,
        name: str,
        route_tier: str,
        decision: PolicyDecision,
        correlation_id: str,
        started: float,
        events: list[OrchestrationEvent],
    ) -> ToolOrchestrationOutcome:
        if decision.requires_approval:
            error = "Explicit human approval is required before this action can execute."
            execution = ExecutionResult.failure(
                action=name,
                error=error,
                risk=decision.effect.value,
                requires_approval=True,
                correlation_id=correlation_id,
            )
            detail = "policy_waiting_for_approval"
        else:
            error = decision.reason or "This action is blocked by local policy."
            execution = ExecutionResult.failure(
                action=name,
                error=error,
                risk=PolicyEffect.BLOCKED.value,
                requires_approval=False,
                correlation_id=correlation_id,
            )
            detail = "policy_blocked_execution"

        payload = {
            "result": error,
            "execution": execution.to_dict(),
            "policy": decision.safe_metadata(),
            "verification_note": (
                "Do not claim this effect succeeded unless execution.can_claim_success is true."
            ),
        }
        duration_ms = max(0, round((time.monotonic() - started) * 1000))
        self._emit(
            events,
            correlation_id,
            AgentStage.FINISH,
            name,
            detail=detail,
            metadata={
                "duration_ms": duration_ms,
                "policy_effect": decision.effect.value,
                "requires_approval": decision.requires_approval,
                "executed": False,
            },
        )
        return ToolOrchestrationOutcome(
            correlation_id=correlation_id,
            tool_name=name,
            raw_response=None,
            response_payload=payload,
            execution=execution,
            events=tuple(events),
            duration_ms=duration_ms,
            route_tier=route_tier,
            policy_effect=decision.effect.value,
            policy_rule=decision.rule_id,
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
