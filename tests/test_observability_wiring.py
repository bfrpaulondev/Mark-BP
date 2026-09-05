from __future__ import annotations

import io
import json
import unittest

from core.agent_orchestrator import AgentOrchestrator
from core.computer_use.contracts import ComputerAction
from core.computer_use.recovery import RecoveryState
from core.cost_telemetry import CostTelemetry, ModelPricing
from core.execution_result import ExecutionResult
from core.providers.contracts import ProviderUsage
from core.structured_logging import configure_logging, redact


class _Response:
    def __init__(self, payload):
        self.response = payload


def _rows(stream: io.StringIO) -> list[dict]:
    return [
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if line.strip()
    ]


class StructuredObservabilityPrivacyTests(unittest.TestCase):
    def test_redaction_is_cycle_safe_bounded_and_content_minimised(self) -> None:
        payload: dict = {
            "prompt": "private prompt",
            "image_bytes": b"123456",
            "api_key": "sk-super-secret-value-1234567890",
            "metadata": [str(index) for index in range(40)],
        }
        payload["cycle"] = payload

        safe = redact(payload)
        serialized = json.dumps(safe, ensure_ascii=False)

        self.assertNotIn("private prompt", serialized)
        self.assertNotIn("super-secret", serialized)
        self.assertIn("[CYCLE]", serialized)
        self.assertIn("[TRUNCATED]", serialized)
        self.assertEqual(safe["image_bytes"]["length"], 6)

    def test_recovery_logging_uses_reason_codes_not_runtime_reason_text(self) -> None:
        stream = io.StringIO()
        configure_logging(stream=stream)
        secret = "person@example.com private recovery detail"
        state = RecoveryState(task_id="cu-observability-test")

        state.note_recovery(f"scroll {secret}")
        state.note_action_retry(ComputerAction(action="scroll"))

        rows = _rows(stream)
        recovery_rows = [row for row in rows if row.get("event") == "computer_use.recovery"]
        self.assertEqual(len(recovery_rows), 2)
        self.assertEqual(recovery_rows[0]["reason_code"], "scroll_no_effect")
        self.assertEqual(recovery_rows[1]["reason_code"], "safe_action_retry")
        self.assertEqual(recovery_rows[1]["retry_count"], 1)
        self.assertTrue(recovery_rows[1]["retry"])
        self.assertNotIn(secret, stream.getvalue())
        self.assertNotIn("person@example.com", stream.getvalue())

    def test_cost_telemetry_logs_attempt_and_task_summary_without_content(self) -> None:
        stream = io.StringIO()
        configure_logging(stream=stream)
        telemetry = CostTelemetry()
        task_id = telemetry.start_task("provider-log-test")
        usage = ProviderUsage(
            input_tokens=100,
            output_tokens=25,
            cached_input_tokens=20,
            total_tokens=125,
        )
        pricing = ModelPricing(
            input_per_million=1.0,
            cached_input_per_million=0.5,
            output_per_million=2.0,
        )

        telemetry.record_provider_attempt(
            task_id,
            provider="openai",
            model="model-test",
            capability="text",
            role="balanced",
            attempt=1,
            ok=True,
            latency_ms=42,
            usage=usage,
            pricing=pricing,
        )
        snapshot = telemetry.finish_task(task_id)

        rows = _rows(stream)
        attempt = next(row for row in rows if row.get("event") == "provider.attempt")
        summary = next(row for row in rows if row.get("event") == "provider.task_finished")

        self.assertEqual(attempt["task_id"], task_id)
        self.assertEqual(attempt["provider"], "openai")
        self.assertEqual(attempt["model"], "model-test")
        self.assertEqual(attempt["attempt"], 1)
        self.assertEqual(attempt["latency_ms"], 42)
        self.assertEqual(attempt["input_tokens"], 100)
        self.assertEqual(attempt["output_tokens"], 25)
        self.assertIsNotNone(attempt["cost_usd"])
        self.assertTrue(summary["cost_complete"])
        self.assertEqual(summary["cost_usd"], snapshot["estimated_cost_usd"])

        serialized = stream.getvalue().lower()
        self.assertNotIn("prompt", serialized)
        self.assertNotIn("image_bytes", serialized)
        self.assertNotIn("response_text", serialized)
        self.assertNotIn("api_key", serialized)


class OrchestratorStructuredObservabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_sink_logs_lifecycle_without_argument_values(self) -> None:
        stream = io.StringIO()
        configure_logging(stream=stream)
        secret = "do-not-log-this-user-text"
        orchestrator = AgentOrchestrator(
            requires_postcondition=lambda name, args: False,
            capture_postcondition_state=lambda name, args: {},
            verify_postcondition=lambda *args, **kwargs: ExecutionResult.verified_success(
                "noop"
            ),
        )

        outcome = await orchestrator.run_tool(
            tool_name="computer_control",
            args={"action": "type", "text": secret},
            executor=lambda: _Response({"result": "done"}),
        )

        rows = _rows(stream)
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(any(row.get("event", "").startswith("agent.route") for row in rows))
        finish = next(row for row in rows if row.get("stage") == "finish")
        self.assertEqual(finish["correlation_id"], outcome.correlation_id)
        self.assertEqual(finish["task_id"], outcome.correlation_id)
        self.assertEqual(finish["tool"], "computer_control")
        self.assertTrue(finish["executed"])
        self.assertTrue(finish["ok"])
        self.assertNotIn(secret, stream.getvalue())
        self.assertNotIn("argument_names", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
