import unittest
from pathlib import Path


class AntonellaExecutionVerifierWiringTests(unittest.TestCase):
    def test_side_effect_tool_responses_flow_through_agent_orchestrator(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "antonella.py").read_text(encoding="utf-8")

        self.assertIn("AgentOrchestrator", source)
        self.assertIn("self._agent_orchestrator = AgentOrchestrator", source)
        self.assertIn("requires_postcondition=requires_postcondition", source)
        self.assertIn("capture_postcondition_state=capture_postcondition_state", source)
        self.assertIn("verify_postcondition=verify_postcondition", source)
        self.assertIn("outcome = await self._agent_orchestrator.run_tool", source)
        self.assertIn("executor=_legacy_executor", source)
        self.assertIn("outcome.response_payload", source)
        self.assertIn("execution.verified", source)

    def test_orchestrator_owns_pre_state_before_legacy_executor_dispatch(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "core" / "agent_orchestrator.py").read_text(encoding="utf-8")

        self.assertLess(
            source.index("self._capture_postcondition_state(name, params)"),
            source.index("raw_response = executor()"),
        )
        self.assertLess(
            source.index("raw_response = executor()"),
            source.index("execution = self._verify_postcondition("),
        )
        self.assertIn('payload["execution"] = execution.to_dict()', source)
        self.assertIn("execution.can_claim_success", source)

    def test_core_prompt_treats_execution_contract_as_authoritative(self):
        root = Path(__file__).resolve().parent.parent
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")

        self.assertIn("execution.can_claim_success=true", prompt)
        self.assertIn("execution.verified=false", prompt)
        self.assertIn("authoritative runtime contract", prompt)


if __name__ == "__main__":
    unittest.main()
