import json
import unittest
from unittest.mock import patch

from core.computer_use.contracts import FrameSnapshot
from core.computer_use.local_perception import LocalPerceptionPlanner


class LocalUiaPerceptionTests(unittest.TestCase):
    def _frame(self) -> FrameSnapshot:
        return FrameSnapshot(
            sequence=1,
            timestamp=1.0,
            left=-100,
            top=50,
            monitor_width=1000,
            monitor_height=500,
            image_width=500,
            image_height=250,
            monitor_index=2,
            change_score=1.0,
            jpeg_bytes=b"not-cached",
            topology_token="topology-1",
            perception_digest="abc123",
        )

    def _inspect(self, controls):
        return json.dumps({"ok": True, "controls": controls})

    def test_unique_explicit_low_risk_control_bypasses_vlm(self):
        planner = LocalPerceptionPlanner()
        response = self._inspect(
            [
                {
                    "name": "Definições",
                    "control_type": "Button",
                    "automation_id": "settings",
                    "class_name": "Button",
                    "enabled": True,
                    "visible": True,
                    "rectangle": [100, 100, 200, 140],
                }
            ]
        )
        with patch(
            "actions.windows_ui_automation.windows_ui_automation",
            return_value=response,
        ) as inspect:
            suggestion = planner.suggest(
                objective="clique em Definições",
                frame=self._frame(),
                target_window="Antonella Test",
            )

        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion.source, "uia")
        self.assertFalse(suggestion.cache_hit)
        self.assertEqual(suggestion.action.action, "click")
        self.assertEqual((suggestion.action.x, suggestion.action.y), (125, 35))
        self.assertEqual(suggestion.action.risk, "low")
        inspect.assert_called_once()

    def test_identical_request_uses_content_minimised_cache(self):
        planner = LocalPerceptionPlanner(ttl_seconds=5.0)
        response = self._inspect(
            [
                {
                    "name": "Ajuda",
                    "control_type": "Hyperlink",
                    "enabled": True,
                    "visible": True,
                    "rectangle": [0, 60, 80, 100],
                }
            ]
        )
        with patch(
            "actions.windows_ui_automation.windows_ui_automation",
            return_value=response,
        ) as inspect:
            first = planner.suggest(
                objective='click "Ajuda"',
                frame=self._frame(),
                target_window="Antonella Test",
            )
            second = planner.suggest(
                objective='click "Ajuda"',
                frame=self._frame(),
                target_window="Antonella Test",
            )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(inspect.call_count, 1)
        cached = next(iter(planner._cache.values()))
        self.assertFalse(hasattr(cached, "name"))
        self.assertFalse(hasattr(cached, "objective"))
        self.assertFalse(hasattr(cached, "window_title"))

    def test_ambiguous_control_falls_through_to_vlm(self):
        planner = LocalPerceptionPlanner()
        control = {
            "name": "Ajuda",
            "control_type": "Button",
            "enabled": True,
            "visible": True,
            "rectangle": [0, 60, 80, 100],
        }
        with patch(
            "actions.windows_ui_automation.windows_ui_automation",
            return_value=self._inspect([control, dict(control)]),
        ):
            suggestion = planner.suggest(
                objective="click Ajuda",
                frame=self._frame(),
                target_window="Antonella Test",
            )
        self.assertIsNone(suggestion)

    def test_risky_or_confirmation_like_target_never_uses_local_click(self):
        planner = LocalPerceptionPlanner()
        with patch(
            "actions.windows_ui_automation.windows_ui_automation"
        ) as inspect:
            self.assertIsNone(
                planner.suggest(
                    objective="click Delete",
                    frame=self._frame(),
                    target_window="Antonella Test",
                )
            )
            self.assertIsNone(
                planner.suggest(
                    objective="clique em Confirmar",
                    frame=self._frame(),
                    target_window="Antonella Test",
                )
            )
        inspect.assert_not_called()

    def test_multistep_natural_language_does_not_trigger_uia_scan(self):
        planner = LocalPerceptionPlanner()
        with patch(
            "actions.windows_ui_automation.windows_ui_automation"
        ) as inspect:
            suggestion = planner.suggest(
                objective="abre as definições e depois muda o tema",
                frame=self._frame(),
                target_window="Antonella Test",
            )
        self.assertIsNone(suggestion)
        inspect.assert_not_called()

    def test_control_outside_current_frame_falls_through(self):
        planner = LocalPerceptionPlanner()
        response = self._inspect(
            [
                {
                    "name": "Ajuda",
                    "control_type": "Button",
                    "enabled": True,
                    "visible": True,
                    "rectangle": [2000, 2000, 2100, 2100],
                }
            ]
        )
        with patch(
            "actions.windows_ui_automation.windows_ui_automation",
            return_value=response,
        ):
            suggestion = planner.suggest(
                objective="click Ajuda",
                frame=self._frame(),
                target_window="Antonella Test",
            )
        self.assertIsNone(suggestion)

    def test_missing_named_target_window_never_uses_foreground_implicitly(self):
        planner = LocalPerceptionPlanner()
        with patch(
            "actions.windows_ui_automation.windows_ui_automation"
        ) as inspect:
            suggestion = planner.suggest(
                objective="click Ajuda",
                frame=self._frame(),
                target_window="",
            )
        self.assertIsNone(suggestion)
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
