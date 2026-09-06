import unittest

from core.human_approval import HumanApprovalManager
from tasks import InMemoryTaskStore, TaskRunner, TaskService, TaskState, TaskStep


class PersistentTaskReviewRegressionTests(unittest.TestCase):
    def test_requires_verification_rejects_plain_ok_as_completion(self):
        store = InMemoryTaskStore()
        service = TaskService(store=store, clock=lambda: 1000.0)
        task = service.create(
            owner_id="u1",
            title="effect",
            steps=[
                TaskStep(
                    name="write",
                    action={"path": "synthetic"},
                    idempotency_key="write-1",
                    requires_verification=True,
                )
            ],
        )
        runner = TaskRunner(store=store, executor=lambda _step: {"ok": True})

        result = runner.run(task)

        self.assertEqual(result.state, TaskState.RECOVERING)
        self.assertEqual(result.steps[0].state, "awaiting_verification")
        self.assertEqual(result.completed_keys, [])

    def test_task_service_approve_grants_exact_pending_dangerous_request(self):
        manager = HumanApprovalManager(clock=lambda: 1000.0)
        store = InMemoryTaskStore()
        service = TaskService(store=store, clock=lambda: 1000.0, approval_manager=manager)
        task = service.create(
            owner_id="u1",
            title="dangerous",
            steps=[
                TaskStep(
                    name="delete",
                    action={"path": "synthetic.txt"},
                    idempotency_key="delete-1",
                    risk="dangerous",
                )
            ],
        )
        calls = []
        runner = TaskRunner(
            store=store,
            executor=lambda _step: calls.append("ran") or {"ok": True},
            approval_manager=manager,
            clock=lambda: 1000.0,
        )

        parked = runner.run(task)
        self.assertEqual(parked.state, TaskState.AWAITING_APPROVAL)
        self.assertTrue(parked.approval_request_id)
        self.assertEqual(calls, [])

        approved = service.approve(task.id, owner_id="u1")
        self.assertEqual(approved.state, TaskState.CREATED)
        self.assertIsNone(approved.approval_request_id)

        final = runner.run(approved)
        self.assertEqual(final.state, TaskState.COMPLETED)
        self.assertEqual(calls, ["ran"])

    def test_lifecycle_transition_without_manager_never_authorizes_dangerous_step(self):
        store = InMemoryTaskStore()
        service = TaskService(store=store, clock=lambda: 1000.0)
        task = service.create(
            owner_id="u1",
            title="dangerous",
            steps=[
                TaskStep(
                    name="delete",
                    action={"path": "synthetic.txt"},
                    idempotency_key="delete-1",
                    risk="dangerous",
                )
            ],
        )
        manager = HumanApprovalManager(clock=lambda: 1000.0)
        calls = []
        runner = TaskRunner(
            store=store,
            executor=lambda _step: calls.append("ran") or {"ok": True},
            approval_manager=manager,
            clock=lambda: 1000.0,
        )
        parked = runner.run(task)
        original_request_id = parked.approval_request_id

        transitioned = service.approve(task.id, owner_id="u1")
        self.assertEqual(transitioned.state, TaskState.CREATED)
        self.assertEqual(transitioned.approval_request_id, original_request_id)

        reparking = runner.run(transitioned)
        self.assertEqual(reparking.state, TaskState.AWAITING_APPROVAL)
        self.assertEqual(calls, [])

    def test_safe_legacy_task_level_approval_remains_compatible(self):
        store = InMemoryTaskStore()
        service = TaskService(store=store, clock=lambda: 1000.0)
        task = service.create(
            owner_id="u1",
            title="review first",
            steps=[TaskStep(name="read", action={}, idempotency_key="read-1")],
            requires_approval=True,
        )

        approved = service.approve(task.id, owner_id="u1")

        self.assertEqual(approved.state, TaskState.CREATED)


if __name__ == "__main__":
    unittest.main()
