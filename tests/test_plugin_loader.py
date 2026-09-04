import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import plugin_loader


VALID_PLUGIN = """
PLUGIN = {
    "name": "echo_test",
    "description": "Echo a supplied value.",
    "parameters": {"type": "OBJECT", "properties": {"value": {"type": "STRING"}}},
}

def run(parameters):
    return parameters.get("value", "")
"""


class PluginLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.plugins_dir = Path(self.temp_dir.name)
        self.logs = []

    def tearDown(self):
        for module_name in list(sys.modules):
            if module_name.startswith("plugins.echo_test"):
                sys.modules.pop(module_name, None)
        self.temp_dir.cleanup()

    def test_valid_plugin_is_discovered_and_executed(self):
        (self.plugins_dir / "echo_test.py").write_text(VALID_PLUGIN, encoding="utf-8")

        with patch.object(plugin_loader, "get_plugin_enabled", return_value=True):
            registry = plugin_loader.discover_plugins(
                self.plugins_dir,
                core_tool_names=set(),
                logger=self.logs.append,
            )

            self.assertTrue(registry.has("echo_test"))
            self.assertEqual(registry.run("echo_test", {"value": "ready"}), "ready")
            self.assertEqual(registry.get_tool_declarations()[0]["name"], "echo_test")

    def test_core_tool_name_collision_is_rejected(self):
        (self.plugins_dir / "echo_test.py").write_text(VALID_PLUGIN, encoding="utf-8")

        registry = plugin_loader.discover_plugins(
            self.plugins_dir,
            core_tool_names={"echo_test"},
            logger=self.logs.append,
        )

        self.assertFalse(registry.has("echo_test"))
        self.assertIn("collides with a core tool", registry.list_for_ui()[0]["error"])

    def test_invalid_plugin_does_not_block_valid_plugins(self):
        (self.plugins_dir / "broken.py").write_text("PLUGIN = {}\n", encoding="utf-8")
        (self.plugins_dir / "echo_test.py").write_text(VALID_PLUGIN, encoding="utf-8")

        registry = plugin_loader.discover_plugins(
            self.plugins_dir,
            core_tool_names=set(),
            logger=self.logs.append,
        )

        records = {record["file"]: record for record in registry.list_for_ui()}
        self.assertTrue(registry.has("echo_test"))
        self.assertFalse(records["broken.py"]["valid"])
        self.assertIn("PLUGIN['name']", records["broken.py"]["error"])

    def test_disabled_plugin_is_not_exposed_or_executed(self):
        (self.plugins_dir / "echo_test.py").write_text(VALID_PLUGIN, encoding="utf-8")
        registry = plugin_loader.discover_plugins(
            self.plugins_dir,
            core_tool_names=set(),
            logger=self.logs.append,
        )

        with patch.object(plugin_loader, "get_plugin_enabled", return_value=False):
            self.assertEqual(registry.get_tool_declarations(), [])
            self.assertIn("disabled", registry.run("echo_test", {"value": "ignored"}))


if __name__ == "__main__":
    unittest.main()
