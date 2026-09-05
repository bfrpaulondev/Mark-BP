import unittest

from tasks import (
    InMemoryTaskStore,
    SchedulerSpec,
    TaskRunner,
    TaskService,
    TaskState,
    TaskStep,
    next_due,
)


def _task_service(steps_spec: list[tuple[str, str]] = None, *, requires_approval: bool = False):
    store = InMemoryTaskStore()
    service = TaskService(store=store, clock=lambda: 1000.0)
    steps = [
        TaskStep(name=name, action={"i": index}, idempotency_key=f"key-{name}", risk=risk)
        for index, (name, risk) in enumerate(steps_spec or [])
    ]
    task = service.create(owner_id="u1", title="Tarefa de teste", steps=steps, requires_approval=requires_approval)
    return service, store, task


def _ok_executor(log: list[str]):
    def executor(step):
        log.append(step.idempotency_key)
        return {"ok": True, "delivered": True}

    return executor


class TaskLifecycleTests(unittest.TestCase):
    def test_happy_path_completes_all_steps(self):
        service, store, task = _task_service([("a", "safe"), ("b", "safe"), ("c", "safe")])
        log: list[str] = []
        runner = TaskRunner(store=store, executor=_ok_executor(log))
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.COMPLETED)
        self.assertEqual(log, ["key-a", "key-b", "key-c"])
        self.assertEqual(result.completed_keys, ["key-a", "key-b", "key-c"])

    def test_requires_approval_blocks_running_until_approved(self):
        service, _, task = _task_service([("a", "safe")], requires_approval=True)
        self.assertEqual(task.state, TaskState.AWAITING_APPROVAL)
        runner = TaskRunner(store=InMemoryTaskStore(), executor=_ok_executor([]))
        with self.assertRaises(ValueError):
            runner.run(task)
        approved = service.approve(task.id, owner_id="u1")
        self.assertEqual(approved.state, TaskState.CREATED)

    def test_failed_step_fails_task_without_inventing_success(self):
        service, store, task = _task_service([("a", "safe"), ("b", "safe")])

        def executor(step):
            if step.name == "b":
                return {"ok": False, "error": "janela não apareceu"}
            return {"ok": True}

        runner = TaskRunner(store=store, executor=executor)
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.FAILED)
        self.assertIn("janela", result.error)
        self.assertEqual(result.completed_keys, ["key-a"])  # step a checkpointed


class CheckpointAndRestartTests(unittest.TestCase):
    def test_restart_never_repeats_checkpointed_effects(self):
        service, store, task = _task_service([("a", "safe"), ("b", "safe"), ("c", "safe")])
        log: list[str] = []
        holder: dict = {}

        def executor(step):
            log.append(step.idempotency_key)
            if holder.get("pause_after_first"):
                holder["runner"].pause()  # takes effect at the next boundary
            return {"ok": True}

        runner = TaskRunner(store=store, executor=executor, clock=lambda: 1000.0)
        holder["runner"] = runner
        holder["pause_after_first"] = True
        result = runner.run(task)  # runs step a, pauses before b
        self.assertEqual(result.state, TaskState.PAUSED)
        self.assertEqual(log, ["key-a"])

        # Simulate a crash: rebuild the store from persisted snapshots.
        snapshots = store.to_dicts()
        store2 = InMemoryTaskStore()
        store2.load_dicts(snapshots)
        rehydrated = store2.get_task(task.id, "u1")
        runner2 = TaskRunner(store=store2, executor=_ok_executor(log))
        final = runner2.run(rehydrated)
        self.assertEqual(final.state, TaskState.COMPLETED)
        self.assertEqual(log, ["key-a", "key-b", "key-c"])  # step a never repeated

    def test_idempotency_key_prevents_duplicate_effects_on_replay(self):
        service, store, task = _task_service([("a", "safe")])
        calls: list[str] = []

        def executor(step):
            calls.append(step.idempotency_key)
            return {"ok": True}

        runner = TaskRunner(store=store, executor=executor)
        runner.run(task)
        self.assertEqual(calls, ["key-a"])
        # Replay in RECOVERING state (the crash-recovery path): done steps
        # and recorded idempotency keys are skipped, effects never duplicate.
        task.state = TaskState.RECOVERING
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.COMPLETED)
        self.assertEqual(calls, ["key-a"])


class CancelPauseRetryTests(unittest.TestCase):
    def test_cancel_between_steps_leaves_task_cancelled(self):
        service, store, task = _task_service([("a", "safe"), ("b", "safe")])
        log: list[str] = []
        runner = TaskRunner(store=store, executor=_ok_executor(log))
        runner.cancel()
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.CANCELLED)
        self.assertEqual(log, [])

    def test_dangerous_steps_never_auto_retry(self):
        service, store, task = _task_service([("del", "dangerous")])
        attempts: list[int] = []

        def executor(step):
            attempts.append(1)
            return {"ok": False, "error_type": "transient"}

        runner = TaskRunner(store=store, executor=executor)
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.FAILED)
        self.assertEqual(len(attempts), 1)

    def test_safe_transient_step_retries_bounded(self):
        service, store, task = _task_service([("a", "safe")])
        attempts: list[int] = []

        def executor(step):
            attempts.append(1)
            if len(attempts) < 3:
                return {"ok": False, "error_type": "timeout"}
            return {"ok": True}

        runner = TaskRunner(store=store, executor=executor)
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.COMPLETED)
        self.assertEqual(len(attempts), 3)  # initial + max_retries=2

    def test_pause_takes_effect_at_step_boundary(self):
        service, store, task = _task_service([("a", "safe"), ("b", "safe")])
        log: list[str] = []
        runner = TaskRunner(store=store, executor=_ok_executor(log))
        runner.pause()
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.PAUSED)
        resumed = service.resume(task.id, owner_id="u1", runner=runner)
        self.assertEqual(resumed.state, TaskState.COMPLETED)


class ReconcileTests(unittest.TestCase):
    def test_reconciler_never_repeats_verified_external_effects(self):
        service, store, task = _task_service([("a", "safe"), ("b", "safe")])
        log: list[str] = []
        runner = TaskRunner(store=store, executor=_ok_executor(log), clock=lambda: 1000.0)

        # Crash simulation: step a ran but was never checkpointed as done.
        task.steps[0].state = "pending"
        store.save_task(task)

        def verifier(step):
            if step.name == "a":
                return {"completed": True, "ok": True}  # effect already happened
            return {"completed": False}

        reconciled = service.reconcile_after_restart(owner_id="u1", state_verifier=verifier, runner=runner)
        self.assertEqual(len(reconciled), 1)
        self.assertEqual(reconciled[0].state, TaskState.COMPLETED)
        self.assertEqual(log, ["key-b"])  # a was reconciled, only b executed


class SchedulerTests(unittest.TestCase):
    def test_once_fires_once(self):
        spec = SchedulerSpec(kind="once", at_epoch=2000.0)
        self.assertEqual(next_due(spec, now=1000.0), 2000.0)
        self.assertIsNone(next_due(spec, now=1000.0, last_run=2000.0))

    def test_interval_from_last_run(self):
        spec = SchedulerSpec(kind="interval", interval_seconds=600)
        self.assertEqual(next_due(spec, now=1000.0, last_run=1500.0), 2100.0)
        self.assertEqual(next_due(spec, now=1000.0), 1000.0)

    def test_daily_respects_timezone_and_no_double_fire(self):
        spec = SchedulerSpec(kind="daily", daily_hour=9, daily_minute=0, tz_offset_minutes=60)
        # 2026-09-06 08:00 UTC = 09:00 local → due now.
        now = 1788672000.0  # 2026-09-06T08:00:00Z (fixed reference)
        due = next_due(spec, now=now, last_run=None)
        local_due = due + spec.tz_offset_minutes * 60
        hour = __import__("datetime").datetime.utcfromtimestamp(local_due).hour
        self.assertEqual(hour, 9)
        # After running at that instant, next due is a day later.
        again = next_due(spec, now=now, last_run=due)
        self.assertEqual(again, due + 86400)


class IsolationTests(unittest.TestCase):
    def test_owner_isolation_on_tasks(self):
        service, store, task = _task_service([("a", "safe")])
        runner = TaskRunner(store=store, executor=_ok_executor([]))
        runner.run(task)
        self.assertIsNone(store.get_task(task.id, owner_id="u2"))
        self.assertEqual(store.list_tasks(owner_id="u2"), [])


if __name__ == "__main__":
    unittest.main()
