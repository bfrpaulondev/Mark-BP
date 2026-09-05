import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.computer_use.contracts import ComputerAction, FrameSnapshot
from core.computer_use.local_perception import LocalPerceptionSuggestion
from core.cost_telemetry import get_cost_telemetry
from core.provider_router import ProviderAttempt


class ComputerUseLocalPerceptionTests(unittest.TestCase):
    def setUp(self):
        get_cost_telemetry().clear()

    def _frame(self) -> FrameSnapshot:
        return FrameSnapshot(
            sequence=1,
            timestamp=1.0,
            left=0,
            top=0,
            monitor_width=1920,
            monitor_height=1080,
            image_width=960,
            image_height=540,
            monitor_index=1,
            change_score=1.0,
            jpeg_bytes=b"private-frame",
            topology_token="topology",
            perception_digest="frame-digest",
        )

    def _config(self):
        return {
            "openai_api_key": "openai-test-key",
            "gemini_api_key": "gemini-test-key",
            "model_provider_preference": "openai",
            "openai_model_fast": "oa-fast",
            "openai_model_balanced": "oa-balanced",
            "openai_model_expert": "oa-expert",
            "computer_use_local_perception_enabled": True,
        }

    def test_first_step_unique_uia_route_skips_provider_and_records_saved_call(self):
        fake_router = MagicMock()
        fake_local = MagicMock()
        fake_local.suggest.return_value = LocalPerceptionSuggestion(
            action=ComputerAction(
                action="click",
                description="Activate unique local UIA Button",
                x=50,
                y=60,
                confidence=1.0,
                risk="low",
            ),
            source="uia",
            cache_hit=False,
        )

        with patch("core.computer_use.planner.ProviderRouter", return_value=fake_router), patch(
            "core.computer_use.planner.LocalPerceptionPlanner",
            return_value=fake_local,
        ):
            from core.computer_use.planner import ComputerUsePlanner

            planner = ComputerUsePlanner(
                self._config(),
                cost_mode="economy",
                target_window="Settings",
            )
            actions = planner.next_actions(
                objective="click Ajuda",
                frame=self._frame(),
                history=[],
                step=1,
            )

        self.assertEqual(actions[0].action, "click")
        fake_router.analyze_image.assert_not_called()
        self.assertEqual(planner.calls, 0)
        self.assertEqual(planner.provider_attempts, 0)
        self.assertEqual(planner.saved_model_calls, 1)
        self.assertEqual(planner.local_perception_routes, 1)
        snapshot = planner.telemetry_snapshot()
        self.assertEqual(snapshot["calls_saved"], 1)
        self.assertEqual(snapshot["cache_hits"], 0)

    def test_cached_uia_route_is_counted_as_cache_hit(self):
        fake_router = MagicMock()
        fake_local = MagicMock()
        fake_local.suggest.return_value = LocalPerceptionSuggestion(
            action=ComputerAction(action="click", x=10, y=10),
            source="uia_cache",
            cache_hit=True,
        )

        with patch("core.computer_use.planner.ProviderRouter", return_value=fake_router), patch(
            "core.computer_use.planner.LocalPerceptionPlanner",
            return_value=fake_local,
        ):
            from core.computer_use.planner import ComputerUsePlanner

            planner = ComputerUsePlanner(
                self._config(),
                target_window="Settings",
            )
            planner.next_actions(
                objective="click Ajuda",
                frame=self._frame(),
                history=[],
                step=1,
            )

        self.assertEqual(planner.perception_cache_hits, 1)
        snapshot = planner.telemetry_snapshot()
        self.assertEqual(snapshot["calls_saved"], 1)
        self.assertEqual(snapshot["cache_hits"], 1)

    def test_after_first_executed_step_planner_reverts_to_vlm_not_cached_click(self):
        fake_router = MagicMock()
        fake_router.analyze_image.return_value = SimpleNamespace(
            text=json.dumps({"actions": [{"action": "done", "result": "ok"}]}),
            provider="openai",
            model="oa-fast",
            fallback_count=0,
            attempts=(
                ProviderAttempt(
                    provider="openai",
                    model="oa-fast",
                    attempt=1,
                    latency_ms=5,
                    ok=True,
                ),
            ),
        )
        fake_local = MagicMock()

        with patch("core.computer_use.planner.ProviderRouter", return_value=fake_router), patch(
            "core.computer_use.planner.LocalPerceptionPlanner",
            return_value=fake_local,
        ):
            from core.computer_use.planner import ComputerUsePlanner

            planner = ComputerUsePlanner(
                self._config(),
                target_window="Settings",
            )
            actions = planner.next_actions(
                objective="click Ajuda",
                frame=self._frame(),
                history=["click: previous local action -> delivered"],
                step=2,
            )

        self.assertEqual(actions[0].action, "done")
        fake_local.suggest.assert_not_called()
        fake_router.analyze_image.assert_called_once()
        self.assertEqual(planner.calls, 1)
        self.assertEqual(planner.provider_attempts, 1)

    def test_disabled_local_perception_goes_directly_to_provider(self):
        fake_router = MagicMock()
        fake_router.analyze_image.return_value = SimpleNamespace(
            text=json.dumps({"actions": [{"action": "done", "result": "ok"}]}),
            provider="openai",
            model="oa-fast",
            fallback_count=0,
            attempts=(
                ProviderAttempt(
                    provider="openai",
                    model="oa-fast",
                    attempt=1,
                    latency_ms=5,
                    ok=True,
                ),
            ),
        )
        config = self._config()
        config["computer_use_local_perception_enabled"] = False

        with patch("core.computer_use.planner.ProviderRouter", return_value=fake_router) as router_cls, patch(
            "core.computer_use.planner.LocalPerceptionPlanner"
        ) as local_cls:
            from core.computer_use.planner import ComputerUsePlanner

            local_instance = local_cls.return_value
            local_instance.suggest.return_value = None
            planner = ComputerUsePlanner(config, target_window="Settings")
            actions = planner.next_actions(
                objective="click Ajuda",
                frame=self._frame(),
                history=[],
                step=1,
            )

        self.assertEqual(actions[0].action, "done")
        self.assertFalse(local_cls.call_args.kwargs["enabled"])
        fake_router.analyze_image.assert_called_once()
        self.assertEqual(planner.saved_model_calls, 0)


if __name__ == "__main__":
    unittest.main()
