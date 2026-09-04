import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import load_config, load_settings, read_legacy_config


class TypedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "api_keys.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    # -.-.-.-
    def test_legacy_json_is_loaded_into_typed_settings(self):
        self.config_file.write_text(
            json.dumps(
                {
                    "assistant_name": "Antonella",
                    "os_system": "Windows",
                    "morning_brief_enabled": False,
                }
            ),
            encoding="utf-8",
        )

        settings = load_settings(self.config_file)

        self.assertEqual(settings.assistant_name, "Antonella")
        self.assertEqual(settings.os_system, "windows")
        self.assertFalse(settings.morning_brief_enabled)

    # -.-.-.-
    def test_environment_overrides_legacy_json(self):
        self.config_file.write_text(
            json.dumps(
                {
                    "assistant_name": "Legacy",
                    "gemini_api_key": "legacy-key-value-123456",
                }
            ),
            encoding="utf-8",
        )

        env = {
            "ANTONELLA_ASSISTANT_NAME": "Antonella",
            "ANTONELLA_GEMINI_API_KEY": "env-key-value-123456",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_config(self.config_file)

        self.assertEqual(config["assistant_name"], "Antonella")
        self.assertEqual(config["gemini_api_key"], "env-key-value-123456")

    # -.-.-.-
    def test_invalid_json_falls_back_to_defaults(self):
        self.config_file.write_text("{invalid", encoding="utf-8")

        self.assertEqual(read_legacy_config(self.config_file), {})
        settings = load_settings(self.config_file)

        self.assertEqual(settings.assistant_name, "JARVIS")
        self.assertIn(settings.os_system, {"windows", "mac", "linux"})

    # -.-.-.-
    def test_unknown_legacy_fields_are_preserved_in_compatibility_dict(self):
        self.config_file.write_text(
            json.dumps({"custom_legacy_value": "keep-me"}),
            encoding="utf-8",
        )

        config = load_config(self.config_file)

        self.assertEqual(config["custom_legacy_value"], "keep-me")


if __name__ == "__main__":
    unittest.main()
