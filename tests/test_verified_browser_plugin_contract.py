import unittest
from pathlib import Path

from plugins import verified_browser_automation as plugin


class VerifiedBrowserPluginContractTests(unittest.TestCase):
    def test_plugin_exposes_verified_managed_browser_actions(self):
        actions = plugin.PLUGIN["parameters"]["properties"]["action"]["description"]
        for action in (
            "go_to",
            "search",
            "click",
            "type",
            "scroll",
            "fill_form",
            "new_tab",
            "close_tab",
            "back",
            "forward",
            "reload",
        ):
            self.assertIn(action, actions)
        self.assertIn("verified boolean", plugin.PLUGIN["description"])

    def test_prompt_separates_real_browser_from_managed_playwright(self):
        root = Path(__file__).resolve().parent.parent
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("verified_browser_automation", prompt)
        self.assertIn("explicitly managed browser session", prompt)
        self.assertIn("already-open real browser", prompt)
        self.assertIn("legacy browser automation compatibility only", prompt)


if __name__ == "__main__":
    unittest.main()
