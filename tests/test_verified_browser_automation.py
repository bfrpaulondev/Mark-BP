import json
import unittest

from actions.verified_browser_automation import (
    _element_state_changed,
    _result,
    _state_changed,
    _url_matches_target,
)
from core.tool_verification_policy import requires_postcondition


class VerifiedBrowserAutomationTests(unittest.TestCase):
    def test_url_match_requires_same_http_origin_and_target_path(self):
        self.assertTrue(
            _url_matches_target(
                "https://example.com/docs/setup?tab=1",
                "https://example.com/docs",
            )
        )
        self.assertFalse(
            _url_matches_target(
                "https://attacker.example/docs",
                "https://example.com/docs",
            )
        )

    def test_page_state_change_is_observable_without_pixels(self):
        before = {
            "url": "https://example.com/a",
            "title": "A",
            "active_tag": "body",
            "active_id": "",
            "page_count": 1,
        }
        after = dict(before, url="https://example.com/b")
        self.assertTrue(_state_changed(before, after))
        self.assertFalse(_state_changed(before, dict(before)))

    def test_element_state_change_detects_common_interaction_effects(self):
        before = {"expanded": "false", "checked": False, "value_length": 0}
        after = {"expanded": "true", "checked": False, "value_length": 0}
        self.assertTrue(_element_state_changed(before, after))
        self.assertFalse(_element_state_changed(before, dict(before)))

    def test_structured_result_is_explicit_and_machine_readable(self):
        payload = json.loads(
            _result(
                "scroll",
                ok=True,
                delivered=True,
                verified=True,
                evidence={"before_y": 0, "after_y": 500},
            )
        )
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["action"], "verified_browser_automation.scroll")

    def test_verified_browser_plugin_always_enters_central_execution_contract(self):
        self.assertTrue(requires_postcondition("verified_browser_automation", {"action": "scroll"}))
        self.assertTrue(requires_postcondition("verified_browser_automation", {"action": "session_status"}))


if __name__ == "__main__":
    unittest.main()
