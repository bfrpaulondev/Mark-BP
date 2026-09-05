import unittest

from core.agent_orchestrator import AgentOrchestrator
from core.execution_result import ExecutionResult
from core.human_approval import HumanApprovalManager


class _Response:
    def __init__(self, payload):
        self.response = payload


class ActionBoundApprovalOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def _orchestrator(self, manager, calls):
        return AgentOrchestrator(
            requires_postcondition=lambda name, args: False,
            capture_postcondition_state=lambda name, args: calls.append("capture") or {},
            verify_postcondition=lambda *args, **kwargs: ExecutionResult.verified_success("noop"),
            approval_manager=manager,
        )

    async def test_exact_local_approval_allows_one_execution_only(self):
        manager = HumanApprovalManager()
        calls = []
        orchestrator = self._orchestrator(manager, calls)
        args = {"action": "delete", "path": "documents/report.txt"}

        pending = await orchestrator.run_tool(
            tool_name="file_controller",
            args=args,
            executor=lambda: calls.append("execute") or _Response({"result": "deleted"}),
        )
        self.assertEqual(calls, [])
        self.assertTrue(pending.execution.requires_approval)
        self.assertTrue(pending.approval_request_id.startswith("apr_"))
        self.assertTrue(manager.approve(pending.approval_request_id))

        allowed = await orchestrator.run_tool(
            tool_name="file_controller",
            args=args,
            executor=lambda: calls.append("execute") or _Response({"result": "deleted"}),
        )
        self.assertEqual(calls, ["execute"])
        self.assertEqual(allowed.response_payload, {"result": "deleted"})
        self.assertIn("trusted_approval_consumed", [event.detail for event in allowed.events])

        again = await orchestrator.run_tool(
            tool_name="file_controller",
            args=args,
            executor=lambda: calls.append("execute-again") or _Response({"result": "deleted"}),
        )
        self.assertEqual(calls, ["execute"])
        self.assertTrue(again.execution.requires_approval)
        self.assertTrue(again.approval_request_id)

    async def test_changed_target_cannot_use_existing_grant(self):
        manager = HumanApprovalManager()
        calls = []
        orchestrator = self._orchestrator(manager, calls)

        first = await orchestrator.run_tool(
            tool_name="file_controller",
            args={"action": "delete", "path": "documents/a.txt"},
            executor=lambda: calls.append("a"),
        )
        self.assertTrue(manager.approve(first.approval_request_id))

        changed = await orchestrator.run_tool(
            tool_name="file_controller",
            args={"action": "delete", "path": "documents/b.txt"},
            executor=lambda: calls.append("b"),
        )
        self.assertEqual(calls, [])
        self.assertTrue(changed.execution.requires_approval)
        self.assertNotEqual(changed.approval_request_id, first.approval_request_id)

    async def test_model_confirmation_fields_do_not_create_a_grant(self):
        manager = HumanApprovalManager()
        calls = []
        orchestrator = self._orchestrator(manager, calls)

        outcome = await orchestrator.run_tool(
            tool_name="file_controller",
            args={
                "action": "delete",
                "path": "documents/report.txt",
                "confirmed": True,
                "approved": True,
                "approval_token": "fabricated",
            },
            executor=lambda: calls.append("execute"),
        )
        self.assertEqual(calls, [])
        self.assertTrue(outcome.execution.requires_approval)
        self.assertTrue(outcome.approval_request_id)


if __name__ == "__main__":
    unittest.main()
