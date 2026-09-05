"""Task runner (ANT-278 F4–F8).

Executes a task's steps with bounded, typed, risk-aware retries (F8),
checkpoint persistence (F4: the task snapshot with done-steps and
completed_keys is saved before the next effect), idempotency (F5),
pause (F6) and cancellation (F7). A crash never repeats an effect nor
invents success.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from tasks.model import Task, TaskEvent, TaskState, TaskStep

Executor = Callable[[TaskStep], dict]  # outcome dict: ok/delivered/verified/error(_type)
STEP_RETRYABLE_ERRORS = frozenset({"timeout", "transient", "unavailable"})


class TaskRunner:
    def __init__(
        self,
        *,
        store,
        executor: Executor,
        clock: Callable[[], float] = time.time,
        event_sink: Callable[[TaskEvent], None] | None = None,
    ):
        self._store = store
        self._executor = executor
        self._clock = clock
        self._event_sink = event_sink
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
    def _run_step(self, task: Task, step: TaskStep) -> dict:
        attempts = 0
        max_retries = 0 if step.risk == "dangerous" else max(0, step.max_retries)
        while True:
            attempts += 1
            try:
                outcome = dict(self._executor(step) or {})
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

            task.state = TaskState.RUNNING
            outcome = self._run_step(task, step)
            step.outcome = outcome
            if outcome.get("ok"):
                step.state = "done"
                task.completed_keys.append(step.idempotency_key)
                self._persist(task)
            else:
                step.state = "failed"
                task.state = TaskState.FAILED
                task.error = str(outcome.get("error") or outcome.get("error_type") or "step failed")
                self._persist(task)
                self._emit(task, "fail", f"{step.name}: {task.error}")
                return task

        task.state = TaskState.COMPLETED
        self._persist(task)
        self._emit(task, "complete", task.title)
        return task
