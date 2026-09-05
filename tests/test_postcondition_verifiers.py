import unittest
from unittest.mock import patch

from core.postcondition_verifiers import (
    _expected_windows_processes,
    verify_open_app_postcondition,
    verify_postcondition,
)


class PostconditionVerifierTests(unittest.TestCase):
    def test_known_windows_app_process_aliases(self):
        self.assertEqual(_expected_windows_processes("Chrome"), {"chrome.exe"})
        self.assertEqual(_expected_windows_processes("Bloco de Notas"), {"notepad.exe"})
        self.assertIn("systemsettings.exe", _expected_windows_processes("Definições"))

    def test_generic_app_name_has_conservative_process_candidate(self):
        self.assertEqual(_expected_windows_processes("My Tool"), {"mytool.exe"})

    @patch("core.postcondition_verifiers.platform.system", return_value="Windows")
    @patch("core.postcondition_verifiers._visible_windows_for_pids")
    @patch("core.postcondition_verifiers._running_process_matches")
    def test_open_app_is_verified_when_expected_process_is_observed(
        self,
        running,
        windows,
        _platform,
    ):
        running.return_value = [{"pid": 42, "process": "chrome.exe"}]
        windows.return_value = [{"hwnd": 99, "pid": 42, "title": "Example - Google Chrome"}]

        result = verify_open_app_postcondition("Chrome")

        self.assertTrue(result.can_claim_success)
        self.assertEqual(result.evidence["processes"][0]["pid"], 42)
        self.assertEqual(result.evidence["visible_windows"][0]["hwnd"], 99)

    @patch("core.postcondition_verifiers.platform.system", return_value="Windows")
    @patch("core.postcondition_verifiers._running_process_matches", return_value=[])
    def test_open_app_fails_when_expected_process_is_not_observed(self, _running, _platform):
        result = verify_open_app_postcondition("Chrome")

        self.assertFalse(result.can_claim_success)
        self.assertFalse(result.ok)
        self.assertTrue(result.delivered)
        self.assertIn("chrome.exe", result.evidence["expected_processes"])

    @patch("core.postcondition_verifiers.verify_open_app_postcondition")
    def test_open_app_domain_verifier_runs_after_legacy_delivery(self, app_verifier):
        from core.execution_result import ExecutionResult

        app_verifier.return_value = ExecutionResult.verified_success("open_app")

        result = verify_postcondition(
            "open_app",
            {"app_name": "Chrome"},
            "Opened Chrome.",
        )

        self.assertTrue(result.can_claim_success)
        app_verifier.assert_called_once_with("Chrome")

    def test_explicit_verified_tool_result_is_not_reverified(self):
        result = verify_postcondition(
            "verified_desktop_control",
            {"action": "mouse_move"},
            '{"ok":true,"delivered":true,"verified":true,"action":"mouse_move","after":[50,60]}',
        )

        self.assertTrue(result.can_claim_success)
        self.assertEqual(result.evidence["after"], [50, 60])


if __name__ == "__main__":
    unittest.main()
