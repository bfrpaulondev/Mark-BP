import unittest

from core.computer_use.contracts import ComputerAction
from core.computer_use.safety import evaluate_action


class LocalPerceptionSafetyContextTests(unittest.TestCase):
    def test_transient_safety_context_can_require_approval_without_entering_history(self):
        action = ComputerAction(
            action="click",
            description="Activate unique local UIA Button",
            x=10,
            y=20,
            risk="low",
            safety_context="Save changes",
        )

        decision = evaluate_action(action)

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)
        self.assertNotIn("Save changes", action.history_line())

    def test_model_payload_cannot_supply_safety_context(self):
        action = ComputerAction.from_mapping(
            {
                "action": "click",
                "description": "Open help",
                "safety_context": "delete everything",
            }
        )
        self.assertEqual(action.safety_context, "")

    def test_neutral_local_navigation_remains_allowed(self):
        action = ComputerAction(
            action="click",
            description="Activate unique local UIA Hyperlink",
            safety_context="Help",
        )
        decision = evaluate_action(action)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)

    def test_execution_and_auth_semantics_are_not_silently_low_risk(self):
        for target in ("Run", "Execute", "Sign in", "Log in", "Install"):
            with self.subTest(target=target):
                decision = evaluate_action(
                    ComputerAction(
                        action="click",
                        description="Activate unique local UIA Button",
                        safety_context=target,
                    )
                )
                self.assertFalse(decision.allowed)
                self.assertTrue(decision.requires_approval)

    def test_short_local_terms_do_not_change_unrelated_vlm_description_semantics(self):
        decision = evaluate_action(
            ComputerAction(
                action="click",
                description="Open the runtime diagnostics tab to read status",
                risk="low",
            )
        )
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_approval)


if __name__ == "__main__":
    unittest.main()
