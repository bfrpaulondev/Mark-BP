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

    def test_dangerous_approval_without_canonical_manager_fails_closed(self):
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
        runner = TaskRunner(
            store=store,
            executor=lambda _step: {"ok": True},
            approval_manager=manager,
            clock=lambda: 1000.0,
        )
        runner.run(task)

        with self.assertRaises(ValueError):
            service.approve(task.id, owner_id="u1")

        self.assertEqual(store.get_task(task.id, "u1").state, TaskState.AWAITING_APPROVAL)

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
