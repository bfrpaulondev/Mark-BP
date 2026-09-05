import json
import unittest
from unittest.mock import patch

from actions.verified_browser_events import (
    _mutation_signal,
    _safe_filename,
    _verify_dom_click,
)
from plugins import verified_browser_automation as plugin


class BrowserEventHelperTests(unittest.TestCase):
    def test_dom_mutation_signal_rejects_background_noise(self):
        self.assertTrue(_mutation_signal(0, 1))
        self.assertTrue(_mutation_signal(1, 1))
        self.assertTrue(_mutation_signal(4, 6))
        self.assertFalse(_mutation_signal(4, 5))
        self.assertFalse(_mutation_signal(0, 0))

    def test_download_filename_is_collapsed_to_safe_leaf(self):
        self.assertEqual(_safe_filename("../report.pdf"), "report.pdf")
        self.assertEqual(_safe_filename("bad:name?.pdf"), "bad_name_.pdf")
        self.assertEqual(_safe_filename("\x00\x01"), "download")

    def test_plugin_exposes_spa_popup_and_download_actions(self):
        action_description = plugin.PLUGIN["parameters"]["properties"]["action"]["description"]
        self.assertIn("click_popup", action_description)
        self.assertIn("click_download", action_description)
        self.assertIn("settle_ms", plugin.PLUGIN["parameters"]["properties"])
        self.assertIn("save_download", plugin.PLUGIN["parameters"]["properties"])

    def test_event_actions_route_to_event_verifier(self):
        with patch.object(plugin, "verified_browser_event_action", return_value='{"verified":true}') as event_control:
            with patch.object(plugin, "verified_browser_automation") as legacy_control:
                result = plugin.run({"action": "click_popup", "description": "Open"})

        self.assertEqual(result, '{"verified":true}')
        event_control.assert_called_once()
        legacy_control.assert_not_called()

    def test_non_event_actions_stay_on_verified_browser_automation(self):
        with patch.object(plugin, "verified_browser_event_action") as event_control:
            with patch.object(plugin, "verified_browser_automation", return_value='{"verified":true}') as browser_control:
                result = plugin.run({"action": "scroll", "direction": "down"})

        self.assertEqual(result, '{"verified":true}')
        browser_control.assert_called_once()
        event_control.assert_not_called()


class _FakeContext:
    def __init__(self):
        self.pages = []


class _FakeLocator:
    def __init__(self, page):
        self.page = page
        self.first = self

    async def count(self):
        return 1

    async def evaluate(self, _script):
        return {
            "checked": False,
            "expanded": None,
            "pressed": None,
            "selected": None,
            "disabled": False,
            "valueLength": None,
        }

    async def click(self, timeout=None):
        self.page.clicked = True


class _FakePage:
    def __init__(self, *, baseline_mutations: int, event_mutations: int):
        self.url = "https://example.test/app"
        self.context = _FakeContext()
        self.context.pages = [self]
        self.clicked = False
        self.baseline_mutations = baseline_mutations
        self.event_mutations = event_mutations
        self.locator_instance = _FakeLocator(self)

    async def title(self):
        return "Example App"

    def locator(self, _selector):
        return self.locator_instance

    def get_by_text(self, _text, exact=False):
        return self.locator_instance

    def get_by_role(self, _role, name=None):
        return self.locator_instance

    async def evaluate(self, script):
        source = str(script)
        if "state.count = 0" in source:
            return 0
        if "Math.min" in source and "__antonellaMutationState" in source:
            return self.event_mutations if self.clicked else self.baseline_mutations
        if "window.scrollX" in source:
            return [0, 0]
        if "document.activeElement" in source:
            return {"tag": "button", "id": "save"}
        return None


class _FakeSession:
    def __init__(self, page):
        self.page = page

    async def _get_page(self):
        return self.page


class BrowserSpaClickTests(unittest.IsolatedAsyncioTestCase):
    async def test_click_is_verified_for_above_noise_dom_mutation(self):
        page = _FakePage(baseline_mutations=0, event_mutations=3)
        result = json.loads(
            await _verify_dom_click(
                _FakeSession(page),
                {"selector": "#save", "settle_ms": 50},
                smart=False,
            )
        )

        self.assertTrue(result["verified"])
        self.assertTrue(result["evidence"]["mutation_signal"])
        self.assertEqual(result["evidence"]["event_mutations"], 3)

    async def test_click_stays_unverified_when_mutation_is_only_background_noise(self):
        page = _FakePage(baseline_mutations=4, event_mutations=5)
        result = json.loads(
            await _verify_dom_click(
                _FakeSession(page),
                {"selector": "#save", "settle_ms": 50},
                smart=False,
            )
        )

        self.assertFalse(result["verified"])
        self.assertFalse(result["evidence"]["mutation_signal"])


if __name__ == "__main__":
    unittest.main()
