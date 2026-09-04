import unittest
from pathlib import Path


class SettingsCenterContractTests(unittest.TestCase):
    def test_settings_center_exposes_runtime_controls(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "ui" / "settings_dialog.py").read_text(encoding="utf-8")

        for label in (
            "PREFERÊNCIAS DA ANTONELLA",
            "Provider",
            "Computer Use",
            "Voz Live",
            "Gemini",
            "OpenAI",
        ):
            self.assertIn(label, source)

        self.assertIn("apply_session_preferences", source)
        self.assertIn("QLineEdit.EchoMode.Password", source)
        self.assertIn("apenas nesta sessão", source)

    def test_existing_ellipsis_is_rebound_to_preferences(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "ui" / "settings_dialog.py").read_text(encoding="utf-8")
        dashboard = (root / "ui" / "runtime_dashboard.py").read_text(encoding="utf-8")

        self.assertIn('button.text() == "•••"', source)
        self.assertIn("bind_settings_button", dashboard)


if __name__ == "__main__":
    unittest.main()
