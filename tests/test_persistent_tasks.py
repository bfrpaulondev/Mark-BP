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
    """Non-verifiable steps: plain ok. Verifiable outcomes must carry
    delivered AND verified (T1)."""
    def executor(step):
        log.append(step.idempotency_key)
        return {"ok": True}

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

    def test_dangerous_steps_require_canonical_grant_and_never_auto_retry(self):
        from core.human_approval import HumanApprovalManager

        service, store, task = _task_service([("del", "dangerous")])
        attempts: list[int] = []

        def executor(step):
            attempts.append(1)
            return {"ok": False, "error_type": "transient"}

        manager = HumanApprovalManager(clock=lambda: 1000.0)
        runner = TaskRunner(store=store, executor=executor, approval_manager=manager, clock=lambda: 1000.0)

        # Fail-closed: no grant -> the task parks awaiting approval.
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.AWAITING_APPROVAL)
        self.assertEqual(attempts, [])

        # Human approves via the canonical manager (request -> one-use
        # grant); the task transitions and the runner consumes the grant
        # exactly once. The transient failure still never auto-retries.
        self.assertTrue(manager.approve(result.approval_request_id))
        approved = service.approve(task.id, owner_id="u1")
        result = runner.run(approved)
        self.assertEqual(result.state, TaskState.FAILED)
        self.assertEqual(len(attempts), 1)

    def test_grant_dies_after_restart_and_re_requests(self):
        from core.human_approval import HumanApprovalManager

        service, store, task = _task_service([("del", "dangerous")])
        attempts: list[int] = []

        def executor(step):
            attempts.append(1)
            return {"ok": True}

        manager = HumanApprovalManager(clock=lambda: 1000.0)
        runner = TaskRunner(store=store, executor=executor, approval_manager=manager, clock=lambda: 1000.0)
        parked = runner.run(task)
        manager.approve(parked.approval_request_id)
        service.approve(task.id, owner_id="u1")

        # Restart: a fresh manager has no provable grant -> parks again.
        snapshots = store.to_dicts()
        store2 = InMemoryTaskStore()
        store2.load_dicts(snapshots)
        fresh_manager = HumanApprovalManager(clock=lambda: 2000.0)
        runner2 = TaskRunner(store=store2, executor=executor, approval_manager=fresh_manager, clock=lambda: 2000.0)
        rehydrated = store2.get_task(task.id, "u1")
        result = runner2.run(rehydrated)
        self.assertEqual(result.state, TaskState.AWAITING_APPROVAL)
        self.assertEqual(attempts, [])  # never ran on trust

    def test_dangerous_step_without_manager_parks_fail_closed(self):
        service, store, task = _task_service([("del", "dangerous")])
        runner = TaskRunner(store=store, executor=_ok_executor([]))
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.AWAITING_APPROVAL)

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


class VerificationContractTests(unittest.TestCase):
    """T1/T2 — delivery is never verification."""

    def _task_with(self, steps_spec):
        store = InMemoryTaskStore()
        service = TaskService(store=store, clock=lambda: 1000.0)
        steps = [TaskStep(name=n, action={}, idempotency_key=f"key-{n}", **kw) for n, kw in steps_spec]
        task = service.create(owner_id="u1", title="T", steps=steps)
        return service, store, task

    def test_plain_ok_step_still_completes(self):
        service, store, task = self._task_with([("query", {})])
        runner = TaskRunner(store=store, executor=lambda s: {"ok": True})
        self.assertEqual(runner.run(task).state, TaskState.COMPLETED)

    def test_delivered_unverified_never_becomes_done(self):
        from core.execution_result import ExecutionResult

        service, store, task = self._task_with([("efeito", {"requires_verification": True})])
        runner = TaskRunner(
            store=store,
            executor=lambda s: ExecutionResult.unverified_delivery(s.name, message="não confirmei"),
        )
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.RECOVERING)
        self.assertEqual(result.steps[0].state, "awaiting_verification")

    def test_verified_execution_result_completes(self):
        from core.execution_result import ExecutionResult

        service, store, task = self._task_with([("efeito", {"requires_verification": True})])
        runner = TaskRunner(
            store=store,
            executor=lambda s: ExecutionResult.verified_success(s.name),
        )
        self.assertEqual(runner.run(task).state, TaskState.COMPLETED)

    def test_parked_verification_blocks_completion(self):
        from core.execution_result import ExecutionResult

        service, store, task = self._task_with(
            [("efeito", {"requires_verification": True}), ("seguinte", {})]
        )
        runner = TaskRunner(
            store=store,
            executor=lambda s: (
                ExecutionResult.unverified_delivery(s.name) if s.name == "efeito" else {"ok": True}
            ),
        )
        result = runner.run(task)
        self.assertEqual(result.state, TaskState.RECOVERING)
        self.assertEqual(result.steps[1].state, "pending")  # never ran past the unverified effect


class ReconcileSafetyTests(unittest.TestCase):
    """T4/T5 — unknown dangerous effects are never replayed on doubt."""

    def test_unknown_dangerous_effect_needs_review(self):
        service, store, task = _task_service([("del", "dangerous"), ("a", "safe")])
        log: list[str] = []
        runner = TaskRunner(store=store, executor=_ok_executor(log), clock=lambda: 1000.0)

        def verifier(step):
            return {"completed": None}  # unknowable

        reconciled = service.reconcile_after_restart(owner_id="u1", state_verifier=verifier, runner=runner)
        result = reconciled[0]
        self.assertEqual(result.steps[0].state, "needs_review")
        self.assertEqual(result.state, TaskState.RECOVERING)
        self.assertEqual(log, ["key-a"])  # safe step ran; dangerous never did

    def test_crash_after_effect_before_checkpoint_is_reconciled(self):
        service, store, task = _task_service([("efeito", {"requires_verification": False, "risk": "safe"})])
        log: list[str] = []
        runner = TaskRunner(store=store, executor=_ok_executor(log), clock=lambda: 1000.0)

        # The effect happened externally but the checkpoint never persisted.
        def verifier(step):
            return {"completed": True, "ok": True}

        reconciled = service.reconcile_after_restart(owner_id="u1", state_verifier=verifier, runner=runner)
        self.assertEqual(reconciled[0].state, TaskState.COMPLETED)
        self.assertEqual(log, [])  # effect NOT repeated


if __name__ == "__main__":
    unittest.main()
