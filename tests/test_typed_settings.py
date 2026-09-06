import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from typing import Any, get_type_hints

from pydantic import ValidationError

from core.voice_runtime import BargeInSettings

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

    def test_environment_secret_is_not_persisted_by_legacy_write_path(self):
        self.config_file.write_text(
            json.dumps(
                {
                    "gemini_api_key": "legacy-key-value-123456",
                    "assistant_name": "Legacy",
                }
            ),
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"ANTONELLA_GEMINI_API_KEY": "env-key-value-123456"},
            clear=False,
        ):
            runtime = load_legacy_compatible_config(self.config_file)
            persisted = read_legacy_config(self.config_file)
            persisted["assistant_name"] = "Antonella"
            write_legacy_config(persisted, self.config_file)
        saved = read_legacy_config(self.config_file)
        self.assertEqual(runtime["gemini_api_key"], "env-key-value-123456")
        self.assertEqual(saved["gemini_api_key"], "legacy-key-value-123456")
        self.assertEqual(saved["assistant_name"], "Antonella")

    def test_provider_models_can_be_overridden_from_environment(self):
        env = {
            "ANTONELLA_OPENAI_API_KEY": "openai-env-key-123456",
            "ANTONELLA_MODEL_PROVIDER_PREFERENCE": "openai",
            "ANTONELLA_OPENAI_MODEL_FAST": "gpt-5.6-luna",
            "ANTONELLA_GEMINI_MODEL_FAST": "gemini-test-fast",
            "ANTONELLA_GEMINI_MODEL_BALANCED": "gemini-test-balanced",
            "ANTONELLA_GEMINI_MODEL_EXPERT": "gemini-test-expert",
            "ANTONELLA_GEMINI_MODEL_CRITIC": "gemini-test-critic",
            "ANTONELLA_GEMINI_MODEL_VISION": "gemini-test-vision",
            "ANTONELLA_COMPUTER_USE_COST_MODE": "economy",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_config(self.config_file)
        self.assertEqual(config["openai_api_key"], "openai-env-key-123456")
        self.assertEqual(config["model_provider_preference"], "openai")
        self.assertEqual(config["openai_model_fast"], "gpt-5.6-luna")
        self.assertEqual(config["gemini_model_fast"], "gemini-test-fast")
        self.assertEqual(config["gemini_model_balanced"], "gemini-test-balanced")
        self.assertEqual(config["gemini_model_expert"], "gemini-test-expert")
        self.assertEqual(config["gemini_model_critic"], "gemini-test-critic")
        self.assertEqual(config["gemini_model_vision"], "gemini-test-vision")
        self.assertEqual(config["computer_use_cost_mode"], "economy")

    def test_invalid_json_falls_back_to_antonella_defaults(self):
        self.config_file.write_text("{invalid", encoding="utf-8")
        self.assertEqual(read_legacy_config(self.config_file), {})
        settings = load_settings(self.config_file)
        self.assertEqual(settings.assistant_name, "Antonella")
        self.assertEqual(settings.voice_name, "Kore")
        self.assertIn("feminine", settings.voice_style)
        self.assertEqual(settings.openai_model_fast, "gpt-5.6-luna")
        self.assertEqual(settings.gemini_model_fast, "gemini-flash-lite-latest")
        self.assertEqual(settings.gemini_model_balanced, "gemini-flash-latest")
        self.assertEqual(settings.gemini_model_vision, "gemini-flash-latest")
        self.assertEqual(settings.computer_use_cost_mode, "economy")
        self.assertIn(settings.os_system, {"windows", "mac", "linux"})

    def test_voice_can_be_overridden_from_environment(self):
        with patch.dict(
            os.environ,
            {"ANTONELLA_VOICE_NAME": "Aoede"},
            clear=False,
        ):
            config = load_config(self.config_file)
        self.assertEqual(config["voice_name"], "Aoede")

    def test_unknown_legacy_fields_are_preserved_in_compatibility_dict(self):
        self.config_file.write_text(
            json.dumps({"custom_legacy_value": "keep-me"}),
            encoding="utf-8",
        )
        config = load_config(self.config_file)
        self.assertEqual(config["custom_legacy_value"], "keep-me")

    # -.-.-.-
    def test_barge_in_defaults_are_typed_and_materialized(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings(self.config_file)
            config = load_config(self.config_file)
        expected = {
            "barge_in_enabled": True, "barge_in_threshold": 900,
            "barge_in_frames": 3, "barge_in_cooldown": 2.0,
        }
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(settings, name), value)
                self.assertEqual(config[name], value)
                self.assertIs(type(config[name]), type(value))

    # -.-.-.-
    def test_barge_in_legacy_values_are_validated_and_materialized(self):
        self.config_file.write_text(json.dumps({
            "barge_in_enabled": "false", "barge_in_threshold": "1200",
            "barge_in_frames": "4", "barge_in_cooldown": "3.5",
        }), encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(self.config_file)
        self.assertIs(config["barge_in_enabled"], False)
        self.assertEqual(config["barge_in_threshold"], 1200)
        self.assertEqual(config["barge_in_frames"], 4)
        self.assertEqual(config["barge_in_cooldown"], 3.5)

    # -.-.-.-
    def test_barge_in_environment_overrides_legacy_values(self):
        self.config_file.write_text(json.dumps({
            "barge_in_enabled": False, "barge_in_threshold": 1200,
            "barge_in_frames": 4, "barge_in_cooldown": 3.5,
        }), encoding="utf-8")
        with patch.dict(os.environ, {
            "ANTONELLA_BARGE_IN_ENABLED": "true",
            "ANTONELLA_BARGE_IN_THRESHOLD": "1600",
            "ANTONELLA_BARGE_IN_FRAMES": "6",
            "ANTONELLA_BARGE_IN_COOLDOWN": "4.5",
        }, clear=True):
            config = load_config(self.config_file)
        self.assertIs(config["barge_in_enabled"], True)
        self.assertEqual(config["barge_in_threshold"], 1600)
        self.assertEqual(config["barge_in_frames"], 6)
        self.assertEqual(config["barge_in_cooldown"], 4.5)

    # -.-.-.-
    def test_invalid_barge_in_values_are_rejected_by_canonical_settings(self):
        for field, value in (
            ("barge_in_enabled", "sometimes"), ("barge_in_threshold", -1),
            ("barge_in_threshold", "loud"), ("barge_in_frames", 0),
            ("barge_in_frames", 1.5), ("barge_in_cooldown", -0.1),
            ("barge_in_cooldown", "nan"), ("barge_in_cooldown", "inf"),
        ):
            for source in ("config", "environment"):
                with self.subTest(field=field, value=value, source=source):
                    self.config_file.write_text(json.dumps(
                        {field: value} if source == "config" else {}
                    ), encoding="utf-8")
                    env = {f"ANTONELLA_{field.upper()}": str(value)} if source == "environment" else {}
                    with patch.dict(os.environ, env, clear=True):
                        with self.assertRaises(ValidationError):
                            load_config(self.config_file)

    # -.-.-.-
    def test_barge_in_value_object_does_not_reresolve_environment_or_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(self.config_file)
        with patch.dict(os.environ, {
            "ANTONELLA_BARGE_IN_ENABLED": "false",
            "ANTONELLA_BARGE_IN_THRESHOLD": "invalid",
        }):
            values = BargeInSettings.from_config(config)
        self.assertEqual(values, BargeInSettings(True, 900, 3, 2.0))
        with self.assertRaises(KeyError):
            BargeInSettings.from_config({})

    # -.-.-.-
    def test_barge_in_annotations_resolve_without_implicit_any(self):
        hints = get_type_hints(BargeInSettings.from_config)
        self.assertEqual(hints["config"], dict[str, Any])
        self.assertIs(hints["return"], BargeInSettings)


if __name__ == "__main__":
    unittest.main()
