import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import (
    load_config,
    load_legacy_compatible_config,
    load_settings,
    read_legacy_config,
    write_legacy_config,
)


class TypedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "api_keys.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_json_is_loaded_into_typed_settings(self):
        self.config_file.write_text(json.dumps({"assistant_name":"Antonella","os_system":"Windows","morning_brief_enabled":False}),encoding="utf-8")
        settings = load_settings(self.config_file)
        self.assertEqual(settings.assistant_name, "Antonella")
        self.assertEqual(settings.os_system, "windows")
        self.assertFalse(settings.morning_brief_enabled)

    def test_environment_overrides_legacy_json(self):
        self.config_file.write_text(json.dumps({"assistant_name":"Legacy","gemini_api_key":"legacy-key-value-123456"}),encoding="utf-8")
        env={"ANTONELLA_ASSISTANT_NAME":"Antonella","ANTONELLA_GEMINI_API_KEY":"env-key-value-123456"}
        with patch.dict(os.environ,env,clear=False):
            config=load_config(self.config_file)
        self.assertEqual(config["assistant_name"],"Antonella")
        self.assertEqual(config["gemini_api_key"],"env-key-value-123456")

    def test_environment_secret_is_not_persisted_by_legacy_write_path(self):
        self.config_file.write_text(json.dumps({"gemini_api_key":"legacy-key-value-123456","assistant_name":"Legacy"}),encoding="utf-8")
        with patch.dict(os.environ,{"ANTONELLA_GEMINI_API_KEY":"env-key-value-123456"},clear=False):
            runtime=load_legacy_compatible_config(self.config_file)
            persisted=read_legacy_config(self.config_file)
            persisted["assistant_name"]="Antonella"
            write_legacy_config(persisted,self.config_file)
        saved=read_legacy_config(self.config_file)
        self.assertEqual(runtime["gemini_api_key"],"env-key-value-123456")
        self.assertEqual(saved["gemini_api_key"],"legacy-key-value-123456")
        self.assertEqual(saved["assistant_name"],"Antonella")

    def test_openai_secret_and_cost_models_can_be_overridden_from_environment(self):
        env={"ANTONELLA_OPENAI_API_KEY":"openai-env-key-123456","ANTONELLA_MODEL_PROVIDER_PREFERENCE":"openai","ANTONELLA_OPENAI_MODEL_FAST":"gpt-5.6-luna","ANTONELLA_COMPUTER_USE_COST_MODE":"economy"}
        with patch.dict(os.environ,env,clear=False):
            config=load_config(self.config_file)
        self.assertEqual(config["openai_api_key"],"openai-env-key-123456")
        self.assertEqual(config["model_provider_preference"],"openai")
        self.assertEqual(config["openai_model_fast"],"gpt-5.6-luna")
        self.assertEqual(config["computer_use_cost_mode"],"economy")

    def test_invalid_json_falls_back_to_antonella_defaults(self):
        self.config_file.write_text("{invalid",encoding="utf-8")
        self.assertEqual(read_legacy_config(self.config_file),{})
        settings=load_settings(self.config_file)
        self.assertEqual(settings.assistant_name,"Antonella")
        self.assertEqual(settings.voice_name,"Kore")
        self.assertIn("feminine",settings.voice_style)
        self.assertEqual(settings.openai_model_fast,"gpt-5.6-luna")
        self.assertEqual(settings.computer_use_cost_mode,"economy")
        self.assertIn(settings.os_system,{"windows","mac","linux"})

    def test_voice_can_be_overridden_from_environment(self):
        with patch.dict(os.environ,{"ANTONELLA_VOICE_NAME":"Aoede"},clear=False):
            config=load_config(self.config_file)
        self.assertEqual(config["voice_name"],"Aoede")

    def test_unknown_legacy_fields_are_preserved_in_compatibility_dict(self):
        self.config_file.write_text(json.dumps({"custom_legacy_value":"keep-me"}),encoding="utf-8")
        config=load_config(self.config_file)
        self.assertEqual(config["custom_legacy_value"],"keep-me")


if __name__ == "__main__":
    unittest.main()
