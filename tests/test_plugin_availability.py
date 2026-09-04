import tempfile
import unittest
from pathlib import Path

from core.plugin_loader import discover_plugins


CONDITIONAL_PLUGIN = """
PLUGIN = {
    "name": "conditional_test",
    "description": "Only available when its local capability is configured.",
    "parameters": {"type": "OBJECT", "properties": {}},
}

def is_available():
    return False

def run(parameters):
    return "should not run"
"""


class PluginAvailabilityTests(unittest.TestCase):
    def test_unavailable_plugin_is_discovered_but_not_exposed_or_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "conditional_test.py").write_text(
                CONDITIONAL_PLUGIN,
                encoding="utf-8",
            )

            registry = discover_plugins(
                plugins_dir=plugins_dir,
                core_tool_names=set(),
                logger=lambda _message: None,
            )

            self.assertTrue(registry.has("conditional_test"))
            self.assertEqual(registry.get_tool_declarations(), [])
            self.assertIn(
                "not available in the current configuration",
                registry.run("conditional_test", {}),
            )
            record = registry.list_for_ui()[0]
            self.assertTrue(record["valid"])
            self.assertFalse(record["available"])


if __name__ == "__main__":
    unittest.main()
