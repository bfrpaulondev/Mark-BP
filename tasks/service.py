"""Task service (ANT-278 F6, F7, F14).

Lifecycle owner: creation, pause/resume, cancel, and post-crash
reconciliation. Reconciliation (F14) never assumes a pending step
succeeded or failed — an external state verifier decides, and only
then does the task continue.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from tasks.model import Task, TaskState, TaskStep
from tasks.runner import TaskRunner
from tasks.store import TaskStore

StateVerifier = Callable[[TaskStep], dict]  # returns {"completed": bool, ...}


class TaskService:
    def __init__(
        self,
        *,
        store: TaskStore,
        clock: Callable[[], float] = time.time,
        approval_manager=None,
    ):
        self._store = store
        self._clock = clock
        self._approval_manager = approval_manager

    # -.-.-.-
    def create(
        self,
        *,
        owner_id: str,
        title: str,
        steps: list[TaskStep],
        project_id: str | None = None,
        requires_approval: bool = False,
    ) -> Task:
        if requires_approval:
            state = TaskState.AWAITING_APPROVAL
        else:
            state = TaskState.CREATED
        now = self._clock()
        task = Task(
            id=uuid.uuid4().hex,
            owner_id=owner_id,
            title=title,
            steps=list(steps),
            state=state,
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )
        self._store.save_task(task)
        return task

    # -.-.-.-
    def approve(self, task_id: str, *, owner_id: str, approval_manager=None) -> Task:
        """Approve the currently pending task gate.

        Dangerous steps use the canonical ``HumanApprovalManager`` request
        created by ``TaskRunner``. This method must approve that exact
        request; merely flipping persisted task state is not authorization.
        Safe legacy task-level approval without a bound dangerous request is
        retained for compatibility, but a dangerous task can never bypass
        the action-bound grant path.
        """
        task = self._require(task_id, owner_id)
        if task.state is not TaskState.AWAITING_APPROVAL:
            raise ValueError(f"task is not awaiting approval (state={task.state.value})")

        manager = approval_manager or self._approval_manager
        dangerous = any(step.risk == "dangerous" and step.state != "done" for step in task.steps)
        if task.approval_request_id:
            if manager is None:
                raise ValueError("canonical approval manager is required for this task")
            if not manager.approve(task.approval_request_id):
                raise ValueError("approval request is unknown or expired")
            task.approval_request_id = None
        elif dangerous:
            raise ValueError("dangerous task has no action-bound approval request")

        task.state = TaskState.CREATED
        task.updated_at = self._clock()
        self._store.save_task(task)
        return task

    # -.-.-.-
    def pause(self, task_id: str, *, owner_id: str, runner: TaskRunner | None = None) -> Task:
        task = self._require(task_id, owner_id)
        if runner is not None:
            runner.pause()  # takes effect at the next step boundary
            return task
        if task.state is TaskState.RUNNING:
            task.state = TaskState.PAUSED
            task.updated_at = self._clock()
            self._store.save_task(task)
        return task

    # -.-.-.-
    def resume(self, task_id: str, *, owner_id: str, runner: TaskRunner) -> Task:
        """F6: resume rehydrates from the persisted snapshot — the runner
        replays only pending steps (completed ones are checkpointed)."""
        task = self._require(task_id, owner_id)
        if task.state is not TaskState.PAUSED:
            raise ValueError(f"cannot resume task in state {task.state.value}")
        return runner.run(task)

    # -.-.-.-
    def cancel(self, task_id: str, *, owner_id: str, runner: TaskRunner | None = None) -> Task:
        """F7: cancellation reaches a running runner via its token, or the
        persisted task directly when it is not mid-flight."""
        task = self._require(task_id, owner_id)
        if task.is_terminal:
            return task
        if runner is not None:
            runner.cancel()
            return task
        task.state = TaskState.CANCELLED
        task.updated_at = self._clock()
        self._store.save_task(task)
        return task

    # -.-.-.-
    def reconcile_after_restart(
        self,
        *,
        owner_id: str,
        state_verifier: StateVerifier,
        runner: TaskRunner,
    ) -> list[Task]:
        """F14/T4/T5: after a crash, verify external reality per pending step.

        Verdicts (``state_verifier`` returns ``{"completed": True/False/None}``):
        - True → the effect already happened: mark done, never re-execute;
        - False → no effect happened: safe steps may re-run via the runner;
        - None (unknown/unverifiable): dangerous steps go to
          ``needs_review`` — they are NEVER re-executed on doubt.
        """
        reconciled: list[Task] = []
        for task in self._store.list_tasks(owner_id, non_terminal_only=True):
            for step in task.steps:
                if step.state != "pending":
                    continue
                verdict = state_verifier(step) or {}
                completed = verdict.get("completed")
                if completed is True:
                    step.state = "done"
                    step.outcome = {k: v for k, v in verdict.items() if k != "completed"}
                    if step.idempotency_key not in task.completed_keys:
                        task.completed_keys.append(step.idempotency_key)
                elif completed is None and step.risk == "dangerous":
                    # T4/T5: an unverified dangerous effect is never replayed
                    # on doubt — it requires human review.
                    step.state = "needs_review"
            if task.state is TaskState.RUNNING:
                task.state = TaskState.RECOVERING
            task.updated_at = self._clock()
            self._store.save_task(task)
            if task.state in (TaskState.RECOVERING, TaskState.PAUSED, TaskState.CREATED):
                reconciled.append(runner.run(task))
        return reconciled

    # -.-.-.-
    def _require(self, task_id: str, owner_id: str) -> Task:
        task = self._store.get_task(task_id, owner_id)
        if task is None:
            raise KeyError(f"task not found for this owner: {task_id}")
        return task
