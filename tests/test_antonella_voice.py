import unittest
from pathlib import Path


class AntonellaVoiceContractTests(unittest.TestCase):
    # -.-.-.-
    def test_default_voice_is_feminine_profile_and_configurable(self):
        root = Path(__file__).resolve().parent.parent
        settings_source = (root / "config" / "settings.py").read_text(encoding="utf-8")
        runtime_source = (root / "antonella.py").read_text(encoding="utf-8")

        self.assertIn('voice_name: str = "Kore"', settings_source)
        self.assertIn("feminine, warm, natural", settings_source)
        self.assertIn('DEFAULT_VOICE = "Kore"', runtime_source)
        self.assertIn('config.get("voice_name")', runtime_source)
        self.assertIn("PrebuiltVoiceConfig(voice_name=voice_name)", runtime_source)

    # -.-.-.-
    def test_antonella_identity_replaces_inherited_jarvis_persona(self):
        root = Path(__file__).resolve().parent.parent
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")

        self.assertIn("ANTONELLA CORE PROTOCOL", prompt)
        self.assertNotIn("Act: Always act like Jarvis", prompt)


if __name__ == "__main__":
    unittest.main()
