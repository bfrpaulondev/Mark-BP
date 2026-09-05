import json
import unittest

from core.plugin_loader import discover_plugins


class RealtimeComputerUsePluginTests(unittest.TestCase):
    def test_plugin_is_discoverable_and_enabled_by_default(self):
        from pathlib import Path

        registry = discover_plugins(
            plugins_dir=Path(__file__).resolve().parent.parent / "plugins",
            core_tool_names=set(),
            logger=lambda _message: None,
        )

        declarations = registry.get_tool_declarations()
        names = {item["name"] for item in declarations}

        self.assertIn("realtime_computer_use", names)

    def test_plugin_description_enforces_cheaper_tools_first(self):
        from plugins.realtime_computer_use import PLUGIN

        description = PLUGIN["description"].lower()
        self.assertIn("only", description)
        self.assertIn("cheaper structured tools", description)
        self.assertIn("rejects stale visual plans", description)
        self.assertNotIn("screenconnect", description)

    def test_plugin_exposes_pause_and_resume_but_not_approval(self):
        from plugins.realtime_computer_use import PLUGIN

        action_description = PLUGIN["parameters"]["properties"]["action"]["description"]
        self.assertIn("pause", action_description)
        self.assertIn("resume", action_description)
        self.assertNotIn("approve", action_description)

    def test_model_callable_approve_is_rejected(self):
        from plugins.realtime_computer_use import run

        result = json.loads(run({"action": "approve"}))
        self.assertFalse(result["ok"])
        self.assertIn("cannot be granted", result["error"])
        self.assertIn("trusted local approval surface", result["error"])


if __name__ == "__main__":
    unittest.main()
