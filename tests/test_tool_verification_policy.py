import unittest

from core.tool_verification_policy import requires_postcondition


class ToolVerificationPolicyTests(unittest.TestCase):
    def test_direct_desktop_effects_require_postconditions(self):
        for name in (
            "open_app",
            "computer_control",
            "computer_settings",
            "verified_desktop_control",
        ):
            self.assertTrue(requires_postcondition(name, {}), name)

    def test_uia_reads_and_effects_are_separated(self):
        self.assertFalse(requires_postcondition("windows_ui_automation", {"action": "list_windows"}))
        self.assertFalse(requires_postcondition("windows_ui_automation", {"action": "inspect"}))
        self.assertFalse(requires_postcondition("windows_ui_automation", {"action": "find"}))
        self.assertTrue(requires_postcondition("windows_ui_automation", {"action": "click"}))
        self.assertTrue(requires_postcondition("windows_ui_automation", {"action": "set_text"}))

    def test_browser_reads_do_not_require_effect_verification(self):
        self.assertFalse(requires_postcondition("browser_control", {"action": "get_text"}))
        self.assertFalse(requires_postcondition("browser_control", {"action": "get_url"}))
        self.assertTrue(requires_postcondition("browser_control", {"action": "click"}))
        self.assertTrue(requires_postcondition("browser_control", {"action": "new_tab"}))

    def test_file_reads_and_mutations_are_separated(self):
        self.assertFalse(requires_postcondition("file_controller", {"action": "read"}))
        self.assertFalse(requires_postcondition("file_controller", {"action": "list"}))
        self.assertTrue(requires_postcondition("file_controller", {"action": "write"}))
        self.assertTrue(requires_postcondition("file_controller", {"action": "delete"}))

    def test_unknown_read_tool_is_not_forced_into_side_effect_contract(self):
        self.assertFalse(requires_postcondition("system_status", {}))
        self.assertFalse(requires_postcondition("expert_reasoning", {}))


if __name__ == "__main__":
    unittest.main()
