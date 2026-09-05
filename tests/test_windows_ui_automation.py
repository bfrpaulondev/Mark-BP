import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from actions.windows_ui_automation import (
    ControlSummary,
    _candidate_score,
    _find_control,
    windows_ui_automation,
)
from plugins.windows_ui_automation import PLUGIN


class _FakeControl:
    def __init__(self, name: str, automation_id: str = "", control_type: str = "Button"):
        self.element_info = SimpleNamespace(
            name=name,
            control_type=control_type,
            automation_id=automation_id,
            class_name=control_type,
            enabled=True,
            visible=True,
        )

    def is_enabled(self):
        return True

    def is_visible(self):
        return True

    def rectangle(self):
        raise RuntimeError("no rectangle in unit test")


class _FakeWindow:
    handle = 42

    def __init__(self, controls):
        self._controls = controls

    def descendants(self):
        return list(self._controls)


class WindowsUIAutomationTests(unittest.TestCase):
    def test_automation_id_has_priority_over_visible_name(self):
        summary = ControlSummary(
            name="Guardar",
            control_type="Button",
            automation_id="saveButton",
            class_name="Button",
            enabled=True,
            visible=True,
            rectangle=(10, 20, 110, 60),
        )

        score = _candidate_score(
            summary,
            name="anything",
            automation_id="saveButton",
            control_type="Button",
        )

        self.assertEqual(score, 0)

    def test_visible_name_matching_is_case_insensitive(self):
        summary = ControlSummary(
            name="Permissões do Utilizador",
            control_type="TabItem",
            automation_id="",
            class_name="",
            enabled=True,
            visible=True,
            rectangle=None,
        )

        score = _candidate_score(summary, name="permissões", control_type="TabItem")

        self.assertEqual(score, 2)

    def test_equally_strong_control_matches_fail_closed(self):
        window = _FakeWindow([_FakeControl("Guardar"), _FakeControl("Guardar")])

        with self.assertRaises(RuntimeError) as exc:
            _find_control(window, name="Guardar")

        self.assertIn("ambiguous", str(exc.exception).lower())

    def test_non_windows_returns_actionable_error_without_importing_pywinauto(self):
        with patch("actions.windows_ui_automation.platform.system", return_value="Linux"):
            result = json.loads(windows_ui_automation({"action": "list_windows"}))

        self.assertFalse(result["ok"])
        self.assertIn("only on Windows", result["error"])

    def test_set_text_re_reads_exact_value_without_exposing_text(self):
        secret = "private-value-123"
        summary = ControlSummary(
            name="Nome",
            control_type="Edit",
            automation_id="nameField",
            class_name="Edit",
            enabled=True,
            visible=True,
            rectangle=None,
        )
        control = Mock()
        window = SimpleNamespace(handle=42)
        before = {
            "control": summary.as_dict(),
            "focused": True,
            "selected": None,
            "toggle_state": None,
            "expand_state": None,
            "value_length": 3,
            "_value": "old",
        }
        after = {**before, "value_length": len(secret), "_value": secret}

        with patch("actions.windows_ui_automation._window_wrapper", return_value=window), \
             patch("actions.windows_ui_automation._refind", side_effect=[(control, summary), (control, summary)]), \
             patch("actions.windows_ui_automation._control_state", side_effect=[before, after]), \
             patch("actions.windows_ui_automation._set_control_text", return_value="set_edit_text"):
            payload = json.loads(
                windows_ui_automation(
                    {
                        "action": "set_text",
                        "automation_id": "nameField",
                        "text": secret,
                    }
                )
            )

        self.assertTrue(payload["verified"])
        self.assertTrue(payload["delivered"])
        self.assertNotIn(secret, json.dumps(payload, ensure_ascii=False))
        self.assertEqual(payload["evidence"]["expected_length"], len(secret))

    def test_set_text_readback_failure_does_not_erase_delivery(self):
        summary = ControlSummary(
            name="Nome",
            control_type="Edit",
            automation_id="nameField",
            class_name="Edit",
            enabled=True,
            visible=True,
            rectangle=None,
        )
        control = Mock()
        window = SimpleNamespace(handle=42)
        before = {
            "control": summary.as_dict(),
            "focused": True,
            "selected": None,
            "toggle_state": None,
            "expand_state": None,
            "value_length": 3,
            "_value": "old",
        }

        with patch("actions.windows_ui_automation._window_wrapper", return_value=window), \
             patch("actions.windows_ui_automation._refind", side_effect=[(control, summary), RuntimeError("gone")]), \
             patch("actions.windows_ui_automation._control_state", return_value=before), \
             patch("actions.windows_ui_automation._set_control_text", return_value="set_edit_text"):
            payload = json.loads(
                windows_ui_automation(
                    {
                        "action": "set_text",
                        "automation_id": "nameField",
                        "text": "replacement",
                    }
                )
            )

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["delivered"])
        self.assertFalse(payload["verified"])
        self.assertTrue(payload["evidence"]["readback_error"])

    def test_click_without_structural_transition_stays_unverified(self):
        summary = ControlSummary(
            name="Actualizar",
            control_type="Button",
            automation_id="refreshButton",
            class_name="Button",
            enabled=True,
            visible=True,
            rectangle=None,
        )
        control = Mock()
        window = SimpleNamespace(handle=42)
        state = {
            "control": summary.as_dict(),
            "focused": False,
            "selected": None,
            "toggle_state": None,
            "expand_state": None,
            "value_length": None,
            "_value": None,
        }

        with patch("actions.windows_ui_automation._window_wrapper", return_value=window), \
             patch("actions.windows_ui_automation._refind", side_effect=[(control, summary), (control, summary)]), \
             patch("actions.windows_ui_automation._control_state", side_effect=[state, state]), \
             patch("actions.windows_ui_automation._activate_control", return_value="invoked"), \
             patch("actions.windows_ui_automation._foreground_handle", side_effect=[42, 42]):
            payload = json.loads(
                windows_ui_automation(
                    {"action": "click", "automation_id": "refreshButton"}
                )
            )

        self.assertTrue(payload["delivered"])
        self.assertFalse(payload["verified"])

    def test_click_focus_and_foreground_changes_are_evidence_not_proof(self):
        summary = ControlSummary(
            name="Abrir",
            control_type="Button",
            automation_id="openButton",
            class_name="Button",
            enabled=True,
            visible=True,
            rectangle=None,
        )
        control = Mock()
        window = SimpleNamespace(handle=42)
        before = {
            "control": summary.as_dict(),
            "focused": False,
            "selected": None,
            "toggle_state": None,
            "expand_state": None,
            "value_length": None,
            "_value": None,
        }
        after = {**before, "focused": True}

        with patch("actions.windows_ui_automation._window_wrapper", return_value=window), \
             patch("actions.windows_ui_automation._refind", side_effect=[(control, summary), (control, summary)]), \
             patch("actions.windows_ui_automation._control_state", side_effect=[before, after]), \
             patch("actions.windows_ui_automation._activate_control", return_value="invoked"), \
             patch("actions.windows_ui_automation._foreground_handle", side_effect=[42, 99]):
            payload = json.loads(
                windows_ui_automation(
                    {"action": "click", "automation_id": "openButton"}
                )
            )

        self.assertTrue(payload["delivered"])
        self.assertFalse(payload["verified"])
        self.assertTrue(payload["evidence"]["foreground_changed"])

    def test_plugin_explicitly_precedes_visual_computer_use(self):
        description = PLUGIN["description"].lower()

        self.assertIn("zero-token", description)
        self.assertIn("before screen vision", description)
        self.assertIn("realtime_computer_use", description)
        self.assertIn("screenconnect", description)


if __name__ == "__main__":
    unittest.main()
