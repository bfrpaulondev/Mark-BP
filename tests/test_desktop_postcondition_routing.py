import unittest
from unittest.mock import patch

from core.execution_result import ExecutionResult
from core.postcondition_verifiers import capture_postcondition_state, verify_postcondition


class DesktopPostconditionRoutingTests(unittest.TestCase):
    @patch("core.postcondition_verifiers.capture_computer_input_state")
    def test_computer_control_input_captures_pre_action_state(self, capture):
        capture.return_value = {"cursor": [10, 20]}

        result = capture_postcondition_state(
            "computer_control",
            {"action": "scroll", "direction": "down", "amount": 3},
        )

        self.assertEqual(result, {"cursor": [10, 20]})
        capture.assert_called_once_with(
            "scroll",
            {"action": "scroll", "direction": "down", "amount": 3},
        )

    @patch("core.postcondition_verifiers.verify_computer_input_postcondition")
    def test_computer_control_input_runs_domain_verifier(self, verifier):
        verifier.return_value = ExecutionResult.verified_success("computer_control.scroll")

        result = verify_postcondition(
            "computer_control",
            {"action": "scroll", "direction": "down"},
            "Scrolled down x3",
            before_state={"frame": {}},
        )

        self.assertTrue(result.can_claim_success)
        verifier.assert_called_once_with(
            "scroll",
            {"action": "scroll", "direction": "down"},
            before_state={"frame": {}},
        )

    @patch("core.postcondition_verifiers.capture_window_setting_state")
    def test_window_setting_captures_target_before_action(self, capture):
        capture.return_value = {"target": {"hwnd": 10}}

        result = capture_postcondition_state(
            "computer_settings",
            {"action": "maximize"},
        )

        self.assertEqual(result, {"target": {"hwnd": 10}})
        capture.assert_called_once_with()

    @patch("core.postcondition_verifiers.verify_window_setting_postcondition")
    def test_window_setting_runs_domain_verifier(self, verifier):
        verifier.return_value = ExecutionResult.verified_success("computer_settings.maximize")

        result = verify_postcondition(
            "computer_settings",
            {"action": "maximize"},
            "Done: maximize.",
            before_state={"target": {"hwnd": 10}},
        )

        self.assertTrue(result.can_claim_success)
        verifier.assert_called_once_with(
            "maximize",
            before_state={"target": {"hwnd": 10}},
        )


if __name__ == "__main__":
    unittest.main()
