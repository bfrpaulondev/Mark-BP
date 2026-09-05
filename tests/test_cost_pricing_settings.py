import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import load_config, load_settings


class CostPricingSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "api_keys.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pricing_table_loads_from_legacy_json_without_defaults(self):
        self.config_file.write_text(
            json.dumps(
                {
                    "model_pricing_usd_per_million_tokens": {
                        "openai/model-x": {
                            "input": 1.0,
                            "output": 4.0,
                            "cached_input": 0.25,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        config = load_config(self.config_file)

        self.assertEqual(
            config["model_pricing_usd_per_million_tokens"]["openai/model-x"]["output"],
            4.0,
        )

    def test_pricing_table_can_be_overridden_by_environment_json(self):
        value = json.dumps(
            {"gemini/model-y": {"input": 0.2, "output": 0.8}}
        )
        with patch.dict(
            os.environ,
            {"ANTONELLA_MODEL_PRICING_USD_PER_MILLION_TOKENS": value},
            clear=False,
        ):
            settings = load_settings(self.config_file)

        self.assertEqual(
            settings.model_pricing_usd_per_million_tokens["gemini/model-y"]["input"],
            0.2,
        )

    def test_pricing_defaults_to_empty_not_invented_prices(self):
        settings = load_settings(self.config_file)
        self.assertEqual(settings.model_pricing_usd_per_million_tokens, {})


if __name__ == "__main__":
    unittest.main()
