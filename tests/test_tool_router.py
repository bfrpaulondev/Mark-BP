import unittest

from core.tool_router import RouteTier, ToolRouter


class ToolRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = ToolRouter()

    def test_direct_local_tools_are_preferred(self):
        route = self.router.route("computer_control", {"action": "scroll"})

        self.assertEqual(route.tier, RouteTier.DIRECT_LOCAL)
        self.assertEqual(route.action, "scroll")

    def test_structured_browser_and_uia_precede_visual_control(self):
        browser = self.router.route("verified_browser_automation", {"action": "click"})
        uia = self.router.route("windows_ui_automation", {"action": "find"})

        self.assertEqual(browser.tier, RouteTier.API_DOM_UIA)
        self.assertEqual(uia.tier, RouteTier.API_DOM_UIA)

    def test_local_cv_precedes_last_resort_computer_use(self):
        local_cv = self.router.route("screenconnect", {"action": "observe"})
        visual = self.router.route("realtime_computer_use", {"action": "run"})

        self.assertEqual(local_cv.tier, RouteTier.LOCAL_CV)
        self.assertEqual(visual.tier, RouteTier.VISION_COMPUTER_USE)

    def test_unknown_tool_stays_on_compatible_legacy_route(self):
        route = self.router.route("existing_plugin", {"action": "custom"})

        self.assertEqual(route.tier, RouteTier.LEGACY)
        self.assertEqual(route.tool_name, "existing_plugin")

    def test_route_metadata_never_contains_argument_values(self):
        secret = "private-secret-value"
        route = self.router.route("file_controller", {"content": secret})

        self.assertNotIn(secret, str(route))


if __name__ == "__main__":
    unittest.main()
