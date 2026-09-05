import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.computer_use.contracts import FrameSnapshot
from core.provider_router import (
    ProviderAttempt,
    ProviderExhaustedError,
    ProviderRole,
)


class ComputerUseProviderRouterTests(unittest.TestCase):
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
        )

    def _config(self):
        return {
            "openai_api_key": "openai-test-key",
            "gemini_api_key": "gemini-test-key",
            "model_provider_preference": "openai",
            "openai_model_fast": "oa-fast",
            "openai_model_balanced": "oa-balanced",
            "openai_model_expert": "oa-expert",
            "gemini_model_fast": "gm-fast",
            "gemini_model_balanced": "gm-balanced",
            "gemini_model_expert": "gm-expert",
        }

    def test_economy_planner_preserves_primary_preference_but_accepts_fallback(self):
        fake_router = MagicMock()
        fake_router.analyze_image.return_value = SimpleNamespace(
            text=json.dumps({"actions": [{"action": "done", "result": "ok"}]}),
            provider="gemini",
            model="gm-fast",
            fallback_count=1,
            attempts=(
                ProviderAttempt(
                    provider="openai",
                    model="oa-fast",
                    attempt=1,
                    latency_ms=20,
                    ok=False,
                    retryable=True,
                    error_type="TimeoutError",
                    error_class="transient_provider",
                ),
                ProviderAttempt(
                    provider="gemini",
                    model="gm-fast",
                    attempt=1,
                    latency_ms=30,
                    ok=True,
                ),
            ),
        )

        with patch(
            "core.computer_use.planner.ProviderRouter",
            return_value=fake_router,
        ):
            from core.computer_use.planner import ComputerUsePlanner

            planner = ComputerUsePlanner(self._config(), cost_mode="economy")
            actions = planner.next_actions(
                objective="finish",
                frame=self._frame(),
                history=[],
                step=1,
            )

        self.assertEqual(actions[0].action, "done")
        kwargs = fake_router.analyze_image.call_args.kwargs
        self.assertEqual(kwargs["role"], ProviderRole.FAST)
        self.assertEqual(kwargs["preference"], "openai")
        self.assertEqual(planner.calls, 1)
        self.assertEqual(planner.provider_attempts, 2)
        self.assertEqual(planner.fallbacks, 1)
        self.assertEqual(planner.last_provider, "gemini")
        self.assertEqual(planner.last_model, "gm-fast")

    def test_balanced_and_quality_map_to_matching_specialist_roles(self):
        from core.computer_use.planner import _provider_role_for_cost_mode

        self.assertEqual(
            _provider_role_for_cost_mode("economy"),
            ProviderRole.FAST,
        )
        self.assertEqual(
            _provider_role_for_cost_mode("balanced"),
            ProviderRole.BALANCED,
        )
        self.assertEqual(
            _provider_role_for_cost_mode("quality"),
            ProviderRole.EXPERT,
        )

    def test_provider_exhaustion_becomes_safe_fail_action_and_counts_attempts(self):
        fake_router = MagicMock()
        attempts = (
            ProviderAttempt(
                provider="openai",
                model="oa-fast",
                attempt=1,
                latency_ms=10,
                ok=False,
                retryable=False,
                error_type="RuntimeError",
                error_class="provider_auth",
            ),
            ProviderAttempt(
                provider="gemini",
                model="gm-fast",
                attempt=1,
                latency_ms=12,
                ok=False,
                retryable=False,
                error_type="RuntimeError",
                error_class="provider_auth",
            ),
        )
        fake_router.analyze_image.side_effect = ProviderExhaustedError(
            attempts,
            eligible_providers=("openai", "gemini"),
        )

        with patch(
            "core.computer_use.planner.ProviderRouter",
            return_value=fake_router,
        ):
            from core.computer_use.planner import ComputerUsePlanner

            planner = ComputerUsePlanner(self._config(), cost_mode="economy")
            actions = planner.next_actions(
                objective="private objective text",
                frame=self._frame(),
                history=[],
                step=1,
            )

        self.assertEqual(actions[0].action, "fail")
        self.assertEqual(planner.provider_attempts, 2)
        self.assertNotIn("private objective text", actions[0].result)
        self.assertNotIn("openai-test-key", actions[0].result)


if __name__ == "__main__":
    unittest.main()
