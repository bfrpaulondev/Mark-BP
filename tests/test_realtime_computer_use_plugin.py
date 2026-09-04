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
        self.assertIn("remote desktops", description)


if __name__ == "__main__":
    unittest.main()
