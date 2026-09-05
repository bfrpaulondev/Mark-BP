import unittest

from core.cost_telemetry import get_cost_telemetry
from core.provider_router import ProviderRouter
from core.providers.contracts import ProviderResponse, ProviderUsage


class _UsageAdapter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_text(self, *, model, prompt, reasoning_effort="low"):
        del model, prompt, reasoning_effort
        self.calls += 1
        event = self.responses.pop(0)
        if isinstance(event, Exception):
            raise event
        return event

    def analyze_image(
        self,
        *,
        model,
        prompt,
        image_bytes,
        mime_type="image/jpeg",
        detail="low",
        reasoning_effort="low",
    ):
        del model, prompt, image_bytes, mime_type, detail, reasoning_effort
        self.calls += 1
        event = self.responses.pop(0)
        if isinstance(event, Exception):
            raise event
        return event


class ProviderRouterCostTelemetryTests(unittest.TestCase):
    def setUp(self):
        get_cost_telemetry().clear()

    def tearDown(self):
        get_cost_telemetry().clear()

    def test_provider_response_usage_is_aggregated_and_priced(self):
        adapter = _UsageAdapter(
            [
                ProviderResponse(
                    text="answer",
                    usage=ProviderUsage(
                        input_tokens=1_000,
                        output_tokens=500,
                        total_tokens=1_500,
                    ),
                )
            ]
        )
        router = ProviderRouter(
            {
                "model_provider_preference": "openai",
                "openai_model_balanced": "priced-model",
                "model_pricing_usd_per_million_tokens": {
                    "openai/priced-model": {"input": 2.0, "output": 4.0}
                },
            },
            adapters={"openai": adapter},
            sleeper=lambda _: None,
        )

        result = router.generate_text(prompt="private prompt", role="balanced")
        snapshot = get_cost_telemetry().snapshot(result.telemetry_task_id)

        self.assertEqual(result.text, "answer")
        self.assertEqual(result.usage.input_tokens, 1_000)
        self.assertTrue(result.cost_complete)
        self.assertEqual(result.task_estimated_cost_usd, 0.004)
        self.assertEqual(snapshot["provider_attempts"], 1)
        self.assertEqual(snapshot["estimated_cost_usd"], 0.004)
        self.assertNotIn("private prompt", str(snapshot))

    def test_string_only_legacy_adapter_remains_compatible_but_cost_unknown(self):
        adapter = _UsageAdapter(["legacy answer"])
        router = ProviderRouter(
            {},
            adapters={"openai": adapter},
            sleeper=lambda _: None,
        )

        result = router.generate_text(prompt="task", role="expert")

        self.assertEqual(result.text, "legacy answer")
        self.assertFalse(result.cost_complete)
        self.assertIsNone(result.task_estimated_cost_usd)

    def test_retry_and_fallback_are_visible_without_error_content(self):
        secret = "PRIVATE-FAILURE-CONTENT"
        openai = _UsageAdapter([RuntimeError(f"HTTP 503 {secret}")])
        gemini = _UsageAdapter(
            [
                ProviderResponse(
                    text="fallback",
                    usage=ProviderUsage(input_tokens=10, output_tokens=5),
                )
            ]
        )
        router = ProviderRouter(
            {"model_provider_preference": "openai"},
            adapters={"openai": openai, "gemini": gemini},
            max_attempts_per_provider=1,
            sleeper=lambda _: None,
        )

        result = router.generate_text(prompt="task", role="balanced")
        snapshot = get_cost_telemetry().snapshot(result.telemetry_task_id)

        self.assertEqual(result.provider, "gemini")
        self.assertEqual(snapshot["provider_attempts"], 2)
        self.assertEqual(snapshot["fallback_attempts"], 1)
        self.assertEqual(snapshot["failed_calls"], 1)
        self.assertNotIn(secret, str(snapshot))

    def test_explicit_task_id_aggregates_multiple_provider_requests(self):
        adapter = _UsageAdapter(
            [
                ProviderResponse(
                    text="one",
                    usage=ProviderUsage(input_tokens=10, output_tokens=2),
                ),
                ProviderResponse(
                    text="two",
                    usage=ProviderUsage(input_tokens=20, output_tokens=3),
                ),
            ]
        )
        router = ProviderRouter(
            {},
            adapters={"gemini": adapter},
            sleeper=lambda _: None,
        )
        telemetry = get_cost_telemetry()
        task_id = telemetry.start_task("shared-task", kind="computer_use")

        first = router.generate_text(
            prompt="one",
            role="fast",
            telemetry_task_id=task_id,
        )
        second = router.generate_text(
            prompt="two",
            role="fast",
            telemetry_task_id=task_id,
        )
        snapshot = telemetry.finish_task(task_id)

        self.assertEqual(first.telemetry_task_id, "shared-task")
        self.assertEqual(second.telemetry_task_id, "shared-task")
        self.assertEqual(snapshot["provider_attempts"], 2)
        self.assertEqual(snapshot["input_tokens"], 30)
        self.assertEqual(snapshot["output_tokens"], 5)


if __name__ == "__main__":
    unittest.main()
