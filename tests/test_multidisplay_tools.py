import unittest

from core.computer_use.contracts import SessionState
from core.display_selection import normalize_monitor_hint
from plugins.display_manager import PLUGIN as DISPLAY_PLUGIN
from plugins.realtime_computer_use import PLUGIN as COMPUTER_USE_PLUGIN


class MultiDisplayToolTests(unittest.TestCase):
    def test_display_manager_is_zero_token_inventory_tool(self):
        description = DISPLAY_PLUGIN["description"].lower()

        self.assertIn("zero-token", description)
        self.assertIn("monitor", description)
        self.assertIn("virtual desktop", description)

    def test_computer_use_accepts_explicit_monitor_target(self):
        properties = COMPUTER_USE_PLUGIN["parameters"]["properties"]

        self.assertIn("monitor", properties)
        self.assertIn("active", properties["monitor"]["description"].lower())
        self.assertIn("all", properties["monitor"]["description"].lower())

    def test_natural_monitor_hint_is_normalized(self):
        self.assertEqual(normalize_monitor_hint("monitor 2"), 2)
        self.assertEqual(normalize_monitor_hint("screen 3"), 3)
        self.assertEqual(normalize_monitor_hint("combined"), "all")
        self.assertIsNone(normalize_monitor_hint("active"))

    def test_session_status_exposes_requested_and_resolved_display(self):
        state = SessionState(
            requested_monitor=2,
            monitor_index=2,
            objective="Inspect the remote application",
        )

        payload = state.as_dict()

        self.assertEqual(payload["requested_monitor"], 2)
        self.assertEqual(payload["monitor_index"], 2)


if __name__ == "__main__":
    unittest.main()
