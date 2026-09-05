import unittest

from core.cost_telemetry import (
    CostTelemetry,
    ModelPricing,
    estimate_usage_cost_usd,
    parse_model_pricing,
    resolve_model_pricing,
)
from core.providers.contracts import ProviderUsage


class _Clock:
    def __init__(self, value=100.0):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


class CostPricingTests(unittest.TestCase):
    def test_estimate_uses_uncached_cached_and_output_rates(self):
        usage = ProviderUsage(
            input_tokens=1_000,
            cached_input_tokens=200,
            output_tokens=500,
            total_tokens=1_500,
        )
        pricing = ModelPricing(
            input_per_million=2.0,
            cached_input_per_million=0.5,
            output_per_million=4.0,
        )

        self.assertEqual(estimate_usage_cost_usd(usage, pricing), 0.0037)

    def test_estimate_uses_provider_normalized_billable_output(self):
        usage = ProviderUsage(
            input_tokens=100,
            output_tokens=20,
            reasoning_tokens=10,
            billable_output_tokens=30,
        )
        pricing = ModelPricing(input_per_million=1.0, output_per_million=2.0)

        self.assertEqual(estimate_usage_cost_usd(usage, pricing), 0.00016)

    def test_missing_required_cached_rate_is_unknown_not_assumed(self):
        usage = ProviderUsage(
            input_tokens=1_000,
            cached_input_tokens=250,
            output_tokens=100,
        )
        pricing = ModelPricing(input_per_million=1.0, output_per_million=2.0)

        self.assertIsNone(estimate_usage_cost_usd(usage, pricing))

    def test_total_only_usage_cannot_be_priced_safely(self):
        usage = ProviderUsage(total_tokens=500)
        pricing = ModelPricing(input_per_million=1.0, output_per_million=2.0)

        self.assertIsNone(estimate_usage_cost_usd(usage, pricing))

    def test_pricing_is_explicitly_resolved_without_defaults(self):
        config = {
            "model_pricing_usd_per_million_tokens": {
                "openai/model-x": {
                    "input": 1.25,
                    "output": 5.0,
                    "cached_input": 0.3,
                }
            }
        }

        pricing = resolve_model_pricing(config, provider="openai", model="model-x")
        self.assertEqual(pricing.input_per_million, 1.25)
        self.assertEqual(pricing.output_per_million, 5.0)
        self.assertEqual(pricing.cached_input_per_million, 0.3)
        self.assertIsNone(
            resolve_model_pricing(config, provider="gemini", model="unknown")
        )

    def test_invalid_negative_nan_and_infinite_prices_are_not_accepted(self):
        self.assertIsNone(parse_model_pricing({"input": -1, "output": "invalid"}))
        self.assertIsNone(parse_model_pricing({"input": "nan"}))
        self.assertIsNone(parse_model_pricing({"output": "inf"}))


class CostTelemetryTaskTests(unittest.TestCase):
    def setUp(self):
        self.wall = _Clock(1_000.0)
        self.mono = _Clock(50.0)
        self.telemetry = CostTelemetry(
            max_tasks=3,
            max_events_per_task=2,
            wall_clock=self.wall,
            monotonic_clock=self.mono,
        )

    def test_task_aggregates_calls_retries_fallback_usage_and_saved_calls(self):
        task_id = self.telemetry.start_task("task-a", kind="computer_use")
        usage = ProviderUsage(input_tokens=100, output_tokens=25, total_tokens=125)
        pricing = ModelPricing(input_per_million=1.0, output_per_million=2.0)

        self.telemetry.record_provider_attempt(
            task_id,
            provider="openai",
            model="model-a",
            capability="vision",
            role="vision",
            attempt=1,
            ok=False,
            latency_ms=90,
            error_class="transient_provider",
        )
        self.telemetry.record_provider_attempt(
            task_id,
            provider="gemini",
            model="model-b",
            capability="vision",
            role="vision",
            attempt=1,
            ok=True,
            latency_ms=110,
            fallback=True,
            usage=usage,
            pricing=pricing,
        )
        self.telemetry.record_saved_call(
            task_id,
            category="computer_use_batch",
            count=2,
        )
        self.telemetry.record_saved_call(task_id, category="cache_hit", count=1)
        self.mono.advance(0.5)
        snapshot = self.telemetry.finish_task(task_id)

        self.assertEqual(snapshot["provider_attempts"], 2)
        self.assertEqual(snapshot["successful_calls"], 1)
        self.assertEqual(snapshot["failed_calls"], 1)
        self.assertEqual(snapshot["fallback_attempts"], 1)
        self.assertEqual(snapshot["calls_saved"], 3)
        self.assertEqual(snapshot["cache_hits"], 1)
        self.assertEqual(snapshot["total_latency_ms"], 200)
        self.assertEqual(snapshot["input_tokens"], 100)
        self.assertEqual(snapshot["output_tokens"], 25)
        self.assertEqual(snapshot["billable_output_tokens"], 25)
        self.assertEqual(snapshot["duration_ms"], 500)
        # Failed provider attempts do not expose authoritative usage/cost, so the
        # overall task estimate stays incomplete rather than pretending precision.
        self.assertFalse(snapshot["cost_complete"])
        self.assertIsNone(snapshot["estimated_cost_usd"])
        self.assertGreater(snapshot["known_cost_usd"], 0)

    def test_all_known_attempts_produce_complete_task_estimate(self):
        task_id = self.telemetry.start_task("task-known")
        self.telemetry.record_provider_attempt(
            task_id,
            provider="openai",
            model="m",
            capability="text",
            role="balanced",
            attempt=1,
            ok=True,
            latency_ms=10,
            usage=ProviderUsage(input_tokens=1_000, output_tokens=500),
            pricing=ModelPricing(input_per_million=2.0, output_per_million=4.0),
        )

        snapshot = self.telemetry.finish_task(task_id)
        self.assertTrue(snapshot["cost_complete"])
        self.assertEqual(snapshot["estimated_cost_usd"], 0.004)

    def test_event_buffer_and_task_registry_are_bounded(self):
        task_id = self.telemetry.start_task("bounded")
        for attempt in range(1, 5):
            self.telemetry.record_provider_attempt(
                task_id,
                provider="openai",
                model="m",
                capability="text",
                role="fast",
                attempt=attempt,
                ok=True,
                latency_ms=1,
                usage=ProviderUsage(input_tokens=1, output_tokens=1),
                pricing=ModelPricing(input_per_million=1.0, output_per_million=1.0),
            )
        self.assertEqual(len(self.telemetry.snapshot(task_id)["events"]), 2)

        for name in ("one", "two", "three", "four"):
            self.telemetry.start_task(name)
        recent_ids = [item["task_id"] for item in self.telemetry.recent_snapshots(limit=10)]
        self.assertEqual(len(recent_ids), 3)
        self.assertNotIn("bounded", recent_ids)

    def test_arbitrary_task_text_is_hashed_instead_of_persisted(self):
        secret = "customer password is hunter2"
        task_id = self.telemetry.start_task(secret)
        snapshot = self.telemetry.snapshot(task_id)

        self.assertTrue(task_id.startswith("task-"))
        self.assertNotIn(secret, task_id)
        self.assertNotIn(secret, str(snapshot))

    def test_snapshot_has_no_arbitrary_content_fields(self):
        task_id = self.telemetry.start_task("privacy")
        self.telemetry.record_provider_attempt(
            task_id,
            provider="openai",
            model="model",
            capability="text",
            role="expert",
            attempt=1,
            ok=False,
            latency_ms=2,
            error_class="provider_auth",
        )
        serialized = str(self.telemetry.snapshot(task_id)).lower()

        self.assertNotIn("prompt", serialized)
        self.assertNotIn("image_bytes", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("response_text", serialized)


if __name__ == "__main__":
    unittest.main()
