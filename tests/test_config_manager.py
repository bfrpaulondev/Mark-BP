import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import config_manager


class ConfigManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name) / "config"
        self.config_file = self.config_dir / "api_keys.json"
        self.patches = [
            patch.object(config_manager, "CONFIG_DIR", self.config_dir),
            patch.object(config_manager, "CONFIG_FILE", self.config_file),
        ]
        for current_patch in self.patches:
            current_patch.start()

    def tearDown(self):
        for current_patch in reversed(self.patches):
            current_patch.stop()
        self.temp_dir.cleanup()

    def test_save_api_key_preserves_existing_settings(self):
        self.config_dir.mkdir(parents=True)
        self.config_file.write_text(
            json.dumps({"assistant_name": "Antonella", "morning_brief_enabled": False}),
            encoding="utf-8",
        )

        config_manager.save_api_keys("  test-key-value-123456  ")

        saved = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["gemini_api_key"], "test-key-value-123456")
        self.assertEqual(saved["assistant_name"], "Antonella")
        self.assertFalse(saved["morning_brief_enabled"])

    def test_invalid_json_returns_empty_configuration(self):
        self.config_dir.mkdir(parents=True)
        self.config_file.write_text("{invalid", encoding="utf-8")

        self.assertEqual(config_manager.load_api_keys(), {})

    def test_plugin_is_enabled_by_default_and_can_be_disabled(self):
        self.assertTrue(config_manager.get_plugin_enabled("example"))

        config_manager.save_plugin_enabled("example", False)

        self.assertFalse(config_manager.get_plugin_enabled("example"))

    def test_assistant_configuration_preserves_api_key(self):
        config_manager.save_api_keys("test-key-value-123456")

        config_manager.save_assistant_config("Antonella", "Bruno")

        saved = config_manager.load_api_keys()
        self.assertEqual(saved["gemini_api_key"], "test-key-value-123456")
        self.assertEqual(saved["assistant_name"], "Antonella")
        self.assertEqual(saved["user_name"], "Bruno")


if __name__ == "__main__":
    unittest.main()
