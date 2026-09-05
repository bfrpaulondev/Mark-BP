import unittest
from unittest.mock import patch

from plugins import verified_desktop_control as plugin


class VerifiedDesktopRealBrowserContractTests(unittest.TestCase):
    def test_plugin_exposes_real_browser_window_tab_and_url_actions(self):
        action_description = plugin.PLUGIN["parameters"]["properties"]["action"]["description"]
        self.assertIn("browser_list_windows", action_description)
        self.assertIn("browser_focus_window", action_description)
        self.assertIn("browser_switch_tab_url", action_description)
        self.assertIn("browser_current", action_description)

        properties = plugin.PLUGIN["parameters"]["properties"]
        self.assertIn("window", properties)
        self.assertIn("url", properties)

    @patch("plugins.verified_desktop_control.real_browser_control", return_value='{"verified":true}')
    @patch("plugins.verified_desktop_control.verified_desktop_control")
    def test_browser_actions_route_to_real_browser_controller(self, legacy_control, real_control):
        result = plugin.run({"action": "browser_list_windows"})

        self.assertEqual(result, '{"verified":true}')
        real_control.assert_called_once()
        legacy_control.assert_not_called()

    @patch("plugins.verified_desktop_control.real_browser_control")
    @patch("plugins.verified_desktop_control.verified_desktop_control", return_value='{"verified":true}')
    def test_mouse_actions_remain_on_verified_mouse_controller(self, mouse_control, real_control):
        result = plugin.run({"action": "mouse_move", "x": 20, "y": 30})

        self.assertEqual(result, '{"verified":true}')
        mouse_control.assert_called_once()
        real_control.assert_not_called()


if __name__ == "__main__":
    unittest.main()
