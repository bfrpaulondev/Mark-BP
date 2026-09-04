import unittest

from core.runtime_snapshot import build_runtime_snapshot


class RuntimeSnapshotTests(unittest.TestCase):
    def test_snapshot_does_not_expose_api_keys(self):
        snapshot = build_runtime_snapshot(
            {
                "openai_api_key": "secret-openai",
                "gemini_api_key": "secret-gemini",
                "computer_use_cost_mode": "economy",
            },
            computer_use_status={"state": "idle"},
            display_status={"displays": []},
        )

        rendered = repr(snapshot)
        self.assertNotIn("secret-openai", rendered)
        self.assertNotIn("secret-gemini", rendered)
        self.assertTrue(snapshot["expert_ready"])
        self.assertEqual(snapshot["cost"], "Económico")

    def test_active_display_is_presented_as_auto(self):
        snapshot = build_runtime_snapshot(
            {"computer_use_cost_mode": "balanced"},
            computer_use_status={"state": "idle"},
            display_status={
                "displays": [
                    {"index": 1, "active": False},
                    {"index": 2, "active": True},
                ]
            },
        )

        self.assertEqual(snapshot["display"], "Ecrã 2 · auto")
        self.assertEqual(snapshot["display_count"], 2)
        self.assertEqual(snapshot["cost"], "Equilibrado")

    def test_running_agent_exposes_only_operational_metadata(self):
        snapshot = build_runtime_snapshot(
            {"computer_use_cost_mode": "quality"},
            computer_use_status={
                "state": "executing",
                "step": 4,
                "model_calls": 2,
                "provider": "openai",
                "model": "gpt-test",
                "monitor_requested": "monitor 3",
                "monitor_index": 3,
            },
            display_status={"displays": [{"index": 3, "active": False}]},
        )

        self.assertEqual(snapshot["agent"], "A executar")
        self.assertEqual(snapshot["agent_detail"], "passo 4 · 2 IA")
        self.assertEqual(snapshot["display"], "Ecrã 3")
        self.assertEqual(snapshot["cost"], "Qualidade")


if __name__ == "__main__":
    unittest.main()
