import unittest
from unittest.mock import patch

from core.execution_result import ExecutionResult
from core.postcondition_verifiers import capture_postcondition_state, verify_postcondition


class Ant258PostconditionRoutingTests(unittest.TestCase):
    @patch("core.postcondition_verifiers.capture_file_state", return_value={"source": {"exists": False}})
    def test_file_mutation_captures_pre_action_state(self, capture):
        args = {"action": "write", "path": "documents/test.txt", "content": "x"}

        state = capture_postcondition_state("file_controller", args)

        self.assertEqual(state, {"source": {"exists": False}})
        capture.assert_called_once_with(args)

    @patch("core.postcondition_verifiers.verify_file_postcondition")
    def test_file_legacy_success_is_rechecked_by_filesystem_verifier(self, verifier):
        verifier.return_value = ExecutionResult.verified_success("file_controller.write")
        args = {"action": "write", "path": "documents/test.txt", "content": "x"}

        result = verify_postcondition(
            "file_controller",
            args,
            "Written to: test.txt",
            before_state={"source": {"exists": False}},
        )

        self.assertTrue(result.can_claim_success)
        verifier.assert_called_once_with(
            args,
            before_state={"source": {"exists": False}},
            delivered=True,
        )

    @patch("core.postcondition_verifiers.capture_settings_state", return_value={"volume_percent": 40})
    def test_observable_setting_captures_pre_action_state(self, capture):
        state = capture_postcondition_state(
            "computer_settings",
            {"action": "volume_set", "value": 60},
        )

        self.assertEqual(state, {"volume_percent": 40})
        capture.assert_called_once_with("volume_set")

    @patch("core.postcondition_verifiers.verify_settings_postcondition")
    def test_observable_setting_legacy_success_is_rechecked(self, verifier):
        verifier.return_value = ExecutionResult.verified_success("computer_settings.volume_set")
        args = {"action": "volume_set", "value": 60}

        result = verify_postcondition(
            "computer_settings",
            args,
            "Volume set to 60%.",
            before_state={"volume_percent": 40},
        )

        self.assertTrue(result.can_claim_success)
        verifier.assert_called_once_with(
            "volume_set",
            args,
            before_state={"volume_percent": 40},
            delivered=True,
        )

    def test_explicit_verified_uia_result_remains_authoritative(self):
        raw = (
            '{"action":"windows_ui_automation.set_text","ok":true,'
            '"delivered":true,"verified":true,"evidence":{"expected_length":5}}'
        )

        result = verify_postcondition(
            "windows_ui_automation",
            {"action": "set_text"},
            raw,
        )

        self.assertTrue(result.can_claim_success)
        self.assertEqual(result.evidence["expected_length"], 5)


if __name__ == "__main__":
    unittest.main()
