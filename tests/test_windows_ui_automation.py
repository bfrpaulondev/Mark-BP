import json
import unittest
from unittest.mock import patch

from actions.windows_ui_automation import (
    ControlSummary,
    _candidate_score,
    windows_ui_automation,
)
from plugins.windows_ui_automation import PLUGIN


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

    def test_non_windows_returns_actionable_error_without_importing_pywinauto(self):
        with patch("actions.windows_ui_automation.platform.system", return_value="Linux"):
            result = json.loads(windows_ui_automation({"action": "list_windows"}))

        self.assertFalse(result["ok"])
        self.assertIn("only on Windows", result["error"])

    def test_plugin_explicitly_precedes_visual_computer_use(self):
        description = PLUGIN["description"].lower()

        self.assertIn("zero-token", description)
        self.assertIn("before screen vision", description)
        self.assertIn("realtime_computer_use", description)
        self.assertIn("screenconnect", description)


if __name__ == "__main__":
    unittest.main()
