import unittest
from unittest.mock import patch

from core.postcondition_verifiers import (
    _expected_windows_processes,
    capture_postcondition_state,
    verify_focus_window_postcondition,
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
    @patch("core.postcondition_verifiers.capture_open_app_state")
    def test_open_app_is_verified_for_new_process_transition(self, capture, _platform):
        capture.return_value = {
            "expected_processes": ["chrome.exe"],
            "processes": [{"pid": 42, "process": "chrome.exe"}],
            "visible_windows": [{"hwnd": 99, "pid": 42, "title": "Chrome"}],
            "foreground": {"hwnd": 99, "pid": 42, "title": "Chrome"},
        }

        result = verify_open_app_postcondition(
            "Chrome",
            before_state={"processes": [], "visible_windows": [], "foreground": {}},
        )

        self.assertTrue(result.can_claim_success)
        self.assertEqual(result.evidence["delta"]["new_process_pids"], [42])
        self.assertEqual(result.evidence["delta"]["new_window_handles"], [99])

    @patch("core.postcondition_verifiers.platform.system", return_value="Windows")
    @patch("core.postcondition_verifiers.capture_open_app_state")
    def test_open_app_existing_process_without_transition_stays_unverified(
        self,
        capture,
        _platform,
    ):
        state = {
            "expected_processes": ["chrome.exe"],
            "processes": [{"pid": 42, "process": "chrome.exe"}],
            "visible_windows": [{"hwnd": 99, "pid": 42, "title": "Chrome"}],
            "foreground": {"hwnd": 99, "pid": 42, "title": "Chrome"},
        }
        capture.return_value = state

        result = verify_open_app_postcondition("Chrome", before_state=state)

        self.assertFalse(result.can_claim_success)
        self.assertTrue(result.ok)
        self.assertTrue(result.delivered)
        self.assertFalse(result.verified)

    @patch("core.postcondition_verifiers.platform.system", return_value="Windows")
    @patch("core.postcondition_verifiers.capture_open_app_state")
    def test_open_app_without_pre_action_state_stays_unverified(self, capture, _platform):
        capture.return_value = {
            "expected_processes": ["chrome.exe"],
            "processes": [{"pid": 42, "process": "chrome.exe"}],
            "visible_windows": [],
            "foreground": {},
        }

        result = verify_open_app_postcondition("Chrome")

        self.assertFalse(result.can_claim_success)
        self.assertTrue(result.ok)
        self.assertIn("pre-action", result.message)

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
            before_state={"processes": []},
        )

        self.assertTrue(result.can_claim_success)
        app_verifier.assert_called_once_with("Chrome", before_state={"processes": []})

    @patch("core.postcondition_verifiers.capture_open_app_state")
    def test_pre_action_capture_is_routed_for_open_app(self, capture):
        capture.return_value = {"processes": []}

        result = capture_postcondition_state("open_app", {"app_name": "Chrome"})

        self.assertEqual(result, {"processes": []})
        capture.assert_called_once_with("Chrome")

    @patch("core.postcondition_verifiers.platform.system", return_value="Windows")
    @patch(
        "core.postcondition_verifiers._foreground_window_snapshot",
        return_value={"hwnd": 7, "pid": 20, "title": "Notas - Bloco de Notas"},
    )
    def test_focus_window_is_verified_against_real_foreground_title(self, _foreground, _platform):
        result = verify_focus_window_postcondition("Bloco de Notas")

        self.assertTrue(result.can_claim_success)
        self.assertEqual(result.evidence["foreground"]["hwnd"], 7)

    @patch("core.postcondition_verifiers.platform.system", return_value="Windows")
    @patch(
        "core.postcondition_verifiers._foreground_window_snapshot",
        return_value={"hwnd": 8, "pid": 30, "title": "Google Chrome"},
    )
    def test_focus_window_fails_when_foreground_is_different(self, _foreground, _platform):
        result = verify_focus_window_postcondition("Bloco de Notas")

        self.assertFalse(result.can_claim_success)
        self.assertTrue(result.delivered)
        self.assertIn("did not match", result.error)

    @patch("core.postcondition_verifiers.verify_focus_window_postcondition")
    def test_focus_window_domain_verifier_is_routed(self, focus_verifier):
        from core.execution_result import ExecutionResult

        focus_verifier.return_value = ExecutionResult.verified_success("computer_control.focus_window")
        result = verify_postcondition(
            "computer_control",
            {"action": "focus_window", "title": "Chrome"},
            "Focused window: Chrome",
        )

        self.assertTrue(result.can_claim_success)
        focus_verifier.assert_called_once_with("Chrome")

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
