import unittest
from pathlib import Path


class AntonellaExecutionVerifierWiringTests(unittest.TestCase):
    def test_side_effect_tool_responses_are_enriched_before_returning_to_model(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "antonella.py").read_text(encoding="utf-8")

        self.assertIn("async def _execute_tool", source)
        self.assertIn("requires_postcondition", source)
        self.assertIn("verify_postcondition", source)
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
