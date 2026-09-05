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
    def __init__(self, *, store: TaskStore, clock: Callable[[], float] = time.time):
        self._store = store
        self._clock = clock

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
    def approve(self, task_id: str, *, owner_id: str) -> Task:
        """F13/T3: approval is explicit and does not linger — the runner
        consumes the canonical one-use grant in the same cycle. The grant
        itself lives in the HumanApprovalManager (in-memory by design):
        after a restart it cannot be proven and the dangerous step
        re-requests approval instead of running."""
        task = self._require(task_id, owner_id)
        if task.state is not TaskState.AWAITING_APPROVAL:
            raise ValueError(f"task is not awaiting approval (state={task.state.value})")
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
