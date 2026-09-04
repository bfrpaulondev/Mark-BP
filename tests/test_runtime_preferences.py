import unittest

from core.runtime_preferences import apply_session_preferences


class RuntimePreferencesTests(unittest.TestCase):
    def test_preferences_apply_to_session_environment_without_returning_secrets(self):
        env = {}
        result = apply_session_preferences(
            gemini_api_key="gemini-secret-value",
            openai_api_key="openai-secret-value",
            cost_mode="balanced",
            provider_preference="openai",
            voice_name="Aoede",
            environ=env,
        )

        self.assertEqual(env["ANTONELLA_GEMINI_API_KEY"], "gemini-secret-value")
        self.assertEqual(env["ANTONELLA_OPENAI_API_KEY"], "openai-secret-value")
        self.assertEqual(env["ANTONELLA_COMPUTER_USE_COST_MODE"], "balanced")
        self.assertEqual(env["ANTONELLA_MODEL_PROVIDER_PREFERENCE"], "openai")
        self.assertEqual(env["ANTONELLA_VOICE_NAME"], "Aoede")

        rendered = repr(result)
        self.assertNotIn("gemini-secret-value", rendered)
        self.assertNotIn("openai-secret-value", rendered)
        self.assertIn("gemini_live", result["restart_required"])
        self.assertIn("expert_tool_schema", result["restart_required"])
        self.assertIn("voice", result["restart_required"])

    def test_empty_secret_fields_keep_existing_keys(self):
        env = {
            "ANTONELLA_GEMINI_API_KEY": "existing-gemini",
            "ANTONELLA_OPENAI_API_KEY": "existing-openai",
        }

        result = apply_session_preferences(
            gemini_api_key="",
            openai_api_key="",
            cost_mode="economy",
            provider_preference="auto",
            voice_name="Kore",
            environ=env,
        )

        self.assertEqual(env["ANTONELLA_GEMINI_API_KEY"], "existing-gemini")
        self.assertEqual(env["ANTONELLA_OPENAI_API_KEY"], "existing-openai")
        self.assertFalse(result["gemini_updated"])
        self.assertFalse(result["openai_updated"])

    def test_invalid_modes_fall_back_to_safe_defaults(self):
        env = {}
        result = apply_session_preferences(
            cost_mode="unlimited",
            provider_preference="unknown",
            environ=env,
        )

        self.assertEqual(result["cost_mode"], "economy")
        self.assertEqual(result["provider_preference"], "auto")


if __name__ == "__main__":
    unittest.main()
