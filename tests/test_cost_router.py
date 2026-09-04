import unittest

from core.cost_router import (
    CostMode,
    budget_for_mode,
    cost_class_for_tool,
    select_visual_route,
)


class CostRouterTests(unittest.TestCase):
    def test_economy_mode_is_strictly_cheaper_than_quality_budget(self):
        economy = budget_for_mode(CostMode.ECONOMY)
        quality = budget_for_mode(CostMode.QUALITY)

        self.assertLess(economy.max_model_calls, quality.max_model_calls)
        self.assertLess(economy.max_steps, quality.max_steps)
        self.assertLess(economy.capture_fps, quality.capture_fps)
        self.assertEqual(economy.image_detail, "low")
        self.assertLess(economy.max_image_width, quality.max_image_width)
        self.assertLess(economy.jpeg_quality, quality.jpeg_quality)

    def test_openai_auto_route_uses_luna_for_economy(self):
        route = select_visual_route(
            {
                "openai_api_key": "test-key",
                "gemini_api_key": "gemini-key",
                "model_provider_preference": "auto",
                "openai_model_fast": "gpt-5.6-luna",
            },
            cost_mode="economy",
        )

        self.assertEqual(route.provider, "openai")
        self.assertEqual(route.model, "gpt-5.6-luna")
        self.assertEqual(route.reasoning_effort, "low")

    def test_gemini_is_fallback_when_openai_is_not_configured(self):
        route = select_visual_route(
            {"gemini_api_key": "gemini-key"},
            cost_mode="economy",
        )

        self.assertEqual(route.provider, "gemini")
        self.assertEqual(route.model, "gemini-flash-lite-latest")

    def test_cost_classes_keep_computer_use_as_last_resort(self):
        self.assertEqual(cost_class_for_tool("open_app"), "local")
        self.assertEqual(cost_class_for_tool("browser_control"), "structured")
        self.assertEqual(cost_class_for_tool("windows_ui_automation"), "structured")
        self.assertEqual(cost_class_for_tool("screen_process"), "vision")
        self.assertEqual(cost_class_for_tool("realtime_computer_use"), "computer_use")


if __name__ == "__main__":
    unittest.main()
