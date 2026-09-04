import unittest
from pathlib import Path


class VerifiedControlContractTests(unittest.TestCase):
    def test_plugin_declares_verified_tab_and_mouse_actions(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "plugins" / "verified_desktop_control.py").read_text(encoding="utf-8")

        for action in (
            "browser_list_tabs",
            "browser_next_tab",
            "browser_previous_tab",
            "browser_switch_tab",
            "mouse_move",
            "mouse_move_relative",
            "mouse_wiggle",
        ):
            self.assertIn(action, source)
        self.assertIn("verified boolean", source)

    def test_prompt_forbids_legacy_false_positive_tab_routing(self):
        root = Path(__file__).resolve().parent.parent
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")

        self.assertIn("EXECUTION EVIDENCE — MANDATORY", prompt)
        self.assertIn("verified=false", prompt)
        self.assertIn("browser_control action='switch'", prompt)
        self.assertIn("verified_desktop_control", prompt)
        self.assertIn("Do NOT use computer_settings next_tab/prev_tab", prompt)


if __name__ == "__main__":
    unittest.main()
