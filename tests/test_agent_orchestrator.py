import unittest

from core.agent_orchestrator import AgentOrchestrator, AgentStage
from core.execution_result import ExecutionResult


class _Response:
    def __init__(self, payload):
        self.response = payload


class AgentOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_side_effect_lifecycle_captures_before_execute_and_verifies_after(self):
        order = []

        def requires(name, args):
            order.append("requires")
            return True

        def capture(name, args):
            order.append("capture")
            return {"before": True}

        def verify(name, args, raw, *, before_state):
            order.append("verify")
            self.assertEqual(before_state, {"before": True})
            self.assertEqual(raw, "legacy-done")
            return ExecutionResult.verified_success(f"{name}.click")

        async def execute():
            order.append("execute")
            return _Response({"result": "legacy-done", "other": 7})

        events = []
        orchestrator = AgentOrchestrator(
            requires_postcondition=requires,
            capture_postcondition_state=capture,
            verify_postcondition=verify,
            event_sink=events.append,
        )

        outcome = await orchestrator.run_tool(
            tool_name="computer_control",
            args={"action": "click", "x": 10, "y": 20},
            executor=execute,
        )

        self.assertEqual(order, ["requires", "capture", "execute", "verify"])
        self.assertEqual(outcome.route_tier, "direct_local")
        self.assertEqual(events[0].metadata["route_tier"], "direct_local")
        self.assertTrue(outcome.execution.can_claim_success)
        self.assertEqual(outcome.response_payload["other"], 7)
        self.assertTrue(outcome.response_payload["execution"]["verified"])
        self.assertEqual(
            outcome.response_payload["execution"]["correlation_id"],
            outcome.correlation_id,
        )
        stages = [event.stage for event in events]
        self.assertEqual(
            stages,
            [
                AgentStage.ROUTE,
                AgentStage.POLICY,
                AgentStage.OBSERVE,
                AgentStage.EXECUTE,
                AgentStage.OBSERVE,
                AgentStage.VERIFY,
                AgentStage.FINISH,
            ],
        )

    async def test_read_only_tool_preserves_original_provider_response(self):
        response = _Response({"result": "42"})
        orchestrator = AgentOrchestrator(
            requires_postcondition=lambda name, args: False,
            capture_postcondition_state=lambda name, args: self.fail("capture should not run"),
            verify_postcondition=lambda *args, **kwargs: self.fail("verify should not run"),
        )

        outcome = await orchestrator.run_tool(
            tool_name="system_status",
            args={},
            executor=lambda: response,
        )

        self.assertIs(outcome.raw_response, response)
        self.assertIsNone(outcome.execution)
        self.assertEqual(outcome.response_payload, {"result": "42"})
        self.assertEqual(
            [event.stage for event in outcome.events],
            [AgentStage.ROUTE, AgentStage.POLICY, AgentStage.EXECUTE, AgentStage.FINISH],
        )

    async def test_unverified_effect_adds_authoritative_verification_note(self):
        orchestrator = AgentOrchestrator(
            requires_postcondition=lambda name, args: True,
            capture_postcondition_state=lambda name, args: {"before": True},
            verify_postcondition=lambda *args, **kwargs: ExecutionResult.unverified_delivery(
                "computer_control.click"
            ),
        )

        outcome = await orchestrator.run_tool(
            tool_name="computer_control",
            args={"action": "click"},
            executor=lambda: _Response({"result": "Done."}),
        )

        self.assertFalse(outcome.can_claim_success)
        self.assertFalse(outcome.response_payload["execution"]["verified"])
        self.assertIn("Do not claim", outcome.response_payload["verification_note"])

    async def test_trace_exposes_argument_names_but_not_sensitive_values(self):
        secret = "private-secret-value"
        orchestrator = AgentOrchestrator(
            requires_postcondition=lambda name, args: False,
            capture_postcondition_state=lambda name, args: {},
            verify_postcondition=lambda *args, **kwargs: ExecutionResult.verified_success("noop"),
        )

        outcome = await orchestrator.run_tool(
            tool_name="send_message",
            args={"message_text": secret, "receiver": "Private Person"},
            executor=lambda: _Response({"result": "ok"}),
        )

        trace_text = str(outcome.trace())
        self.assertIn("message_text", trace_text)
        self.assertIn("receiver", trace_text)
        self.assertNotIn(secret, trace_text)
        self.assertNotIn("Private Person", trace_text)

    async def test_executor_exception_is_not_swallowed(self):
        events = []
        orchestrator = AgentOrchestrator(
            requires_postcondition=lambda name, args: False,
            capture_postcondition_state=lambda name, args: {},
            verify_postcondition=lambda *args, **kwargs: ExecutionResult.verified_success("noop"),
            event_sink=events.append,
        )

        async def explode():
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            await orchestrator.run_tool(tool_name="broken", args={}, executor=explode)

        self.assertEqual(events[-1].stage, AgentStage.FAILED)
        self.assertEqual(events[-1].metadata["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
