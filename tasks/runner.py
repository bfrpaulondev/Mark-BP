"""Task runner (ANT-278 F4–F8, hardened T1–T5).

Executes a task's steps with bounded, typed, risk-aware retries (F8),
checkpoint persistence (F4: the task snapshot with done-steps and
completed_keys is saved before the next effect), idempotency (F5),
pause (F6) and cancellation (F7). A crash never repeats an effect nor
invents success.

T1/T2: delivery is never verification — a verifiable step only becomes
"done" with delivered AND verified; delivered-but-unverified parks in
``awaiting_verification`` and the task enters RECOVERING.

T3: dangerous steps consume a one-use grant from the canonical
``HumanApprovalManager`` (fingerprint-bound, TTL, dies on restart);
without a provable grant the task parks in AWAITING_APPROVAL.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from core.execution_result import ExecutionResult
from tasks.model import Task, TaskEvent, TaskState, TaskStep

Executor = Callable[[TaskStep], Any]  # dict outcome or ExecutionResult
STEP_RETRYABLE_ERRORS = frozenset({"timeout", "transient", "unavailable"})
BLOCKED_STEP_STATES = frozenset({"awaiting_verification", "awaiting_approval", "needs_review"})


class TaskRunner:
    def __init__(
        self,
        *,
        store,
        executor: Executor,
        clock: Callable[[], float] = time.time,
        event_sink: Callable[[TaskEvent], None] | None = None,
        approval_manager=None,  # canonical HumanApprovalManager (T3), optional
    ):
        self._store = store
        self._executor = executor
        self._clock = clock
        self._event_sink = event_sink
        self._approval_manager = approval_manager
        self._cancel = threading.Event()
        self._pause = threading.Event()

    # -.-.-.-
    def cancel(self) -> None:
        self._cancel.set()

    def pause(self) -> None:
        self._pause.set()

    # -.-.-.-
    def _emit(self, task: Task, kind: str, message: str) -> None:
        if self._event_sink:
            self._event_sink(TaskEvent(timestamp=self._clock(), kind=kind, message=message))

    # -.-.-.-
    def _persist(self, task: Task) -> None:
        task.updated_at = self._clock()
        self._store.save_task(task)  # the saved snapshot IS the checkpoint (F4)

    # -.-.-.-
    def _classify(self, step: TaskStep, outcome: Any) -> str:
        """T1: delivery is never verification.

        Verifiable outcomes (ExecutionResult or a dict carrying
        delivered/verified) require delivered AND verified for ``done``.
        If the step contract itself requires verification, a legacy/plain
        ``{"ok": true}`` outcome is insufficient and parks for verification
        rather than silently completing.
        """
        if isinstance(outcome, ExecutionResult):
            if outcome.can_claim_success:
                return "done"
            if outcome.ok and outcome.delivered and not outcome.verified:
                return "awaiting_verification"
            return "failed"
        if not isinstance(outcome, dict):
            return "failed"
        if "delivered" in outcome or "verified" in outcome:
            if outcome.get("ok") and outcome.get("delivered") and outcome.get("verified"):
                return "done"
            if outcome.get("ok") and outcome.get("delivered") and not outcome.get("verified"):
                return "awaiting_verification"
            return "failed"
        if step.requires_verification and outcome.get("ok"):
            return "awaiting_verification"
        return "done" if outcome.get("ok") else "failed"

    # -.-.-.-
    def _approval_gate(self, task: Task, step: TaskStep) -> bool:
        """T3: dangerous steps consume a one-use grant from the canonical
        approval manager, fingerprint-bound to the exact step action.
        Fail-closed: without a manager or without a provable grant the
        step parks in AWAITING_APPROVAL — it never runs on trust."""
        if step.risk != "dangerous":
            return True
        if self._approval_manager is None:
            return False
        from core.policy_engine import PolicyDecision, PolicyEffect

        decision = PolicyDecision(
            effect=PolicyEffect.DESTRUCTIVE,
            allowed=True,
            requires_approval=True,
            rule_id="task.dangerous_step",
            reason=f"dangerous task step: {step.name}",
        )
        if self._approval_manager.consume_if_approved(step.name, step.action, decision):
            task.approval_request_id = None
            return True
        request = self._approval_manager.request(step.name, step.action, decision)
        task.approval_request_id = request.request_id
        return False

    # -.-.-.-
    def _run_step(self, task: Task, step: TaskStep) -> Any:
        attempts = 0
        max_retries = 0 if step.risk == "dangerous" else max(0, step.max_retries)
        while True:
            attempts += 1
            try:
                outcome = self._executor(step)
                if isinstance(outcome, ExecutionResult):
                    if outcome.ok:
                        return outcome
                    error_type = str(outcome.error or "error")
                    if attempts <= max_retries and error_type in STEP_RETRYABLE_ERRORS:
                        self._emit(task, "retry", f"{step.name} retry {attempts}/{max_retries}")
                        continue
                    return outcome
                outcome = dict(outcome or {})
                if outcome.get("ok"):
                    return outcome
                error_type = str(outcome.get("error_type") or "error")
                if attempts <= max_retries and error_type in STEP_RETRYABLE_ERRORS:
                    self._emit(task, "retry", f"{step.name} retry {attempts}/{max_retries}")
                    continue
                return outcome
            except Exception as exc:  # noqa: BLE001 - crash classification is explicit
                error_type = type(exc).__name__
                if attempts <= max_retries and error_type in STEP_RETRYABLE_ERRORS:
                    self._emit(task, "retry", f"{step.name} retry {attempts}/{max_retries}")
                    continue
                return {"ok": False, "error_type": error_type, "error": str(exc)}

    # -.-.-.-
    def run(self, task: Task) -> Task:
        if task.state is TaskState.CREATED:
            task.state = TaskState.RUNNING
            self._persist(task)
        elif task.state is not TaskState.PAUSED and task.state is not TaskState.RECOVERING:
            raise ValueError(f"cannot run task in state {task.state.value}")

        for step in task.steps:
            if self._cancel.is_set():
                task.state = TaskState.CANCELLED
                step.state = "cancelled" if step.state == "pending" else step.state
                self._persist(task)
                self._emit(task, "cancel", task.title)
                return task
            if self._pause.is_set():
                self._pause.clear()
                task.state = TaskState.PAUSED
                self._persist(task)
                self._emit(task, "pause", task.title)
                return task
            if step.state == "done" or step.idempotency_key in task.completed_keys:
                continue  # F4: checkpointed effects never repeat
            if step.state in ("needs_review", "cancelled", "awaiting_verification"):
                continue  # human/verification-gated steps never auto-execute

            task.state = TaskState.RUNNING

            # T3: the grant gate runs on EVERY execution attempt of a
            # dangerous step — a parked step must never bypass it after a
            # restart (the in-memory grant cannot be proven, so a fresh
            # request is issued instead of running on trust).
            if step.risk == "dangerous":
                if not self._approval_gate(task, step):
                    step.state = "awaiting_approval"
                    task.state = TaskState.AWAITING_APPROVAL
                    self._persist(task)
                    self._emit(task, "awaiting_approval", step.name)
                    return task

            outcome = self._run_step(task, step)
            step.outcome = outcome.to_dict() if isinstance(outcome, ExecutionResult) else dict(outcome or {})
            verdict = self._classify(step, outcome)

            if verdict == "done":
                step.state = "done"
                if step.idempotency_key not in task.completed_keys:
                    task.completed_keys.append(step.idempotency_key)
                self._persist(task)
            elif verdict == "awaiting_verification":
                step.state = "awaiting_verification"
                task.state = TaskState.RECOVERING
                self._persist(task)
                self._emit(task, "awaiting_verification", step.name)
                return task
            else:
                step.state = "failed"
                task.state = TaskState.FAILED
                if isinstance(outcome, ExecutionResult):
                    task.error = str(outcome.error or "step failed")
                else:
                    task.error = str(outcome.get("error") or outcome.get("error_type") or "step failed")
                self._persist(task)
                self._emit(task, "fail", f"{step.name}: {task.error}")
                return task

        blocked = [s for s in task.steps if s.state in BLOCKED_STEP_STATES]
        if blocked:
            task.state = TaskState.RECOVERING
            self._persist(task)
            self._emit(task, "blocked", ", ".join(s.name for s in blocked))
            return task
        task.state = TaskState.COMPLETED
        self._persist(task)
        self._emit(task, "complete", task.title)
        return task
