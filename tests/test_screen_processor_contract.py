import unittest
from pathlib import Path


class ScreenProcessorContractTests(unittest.TestCase):
    # -.-.-.-
    def test_vision_uses_dynamic_antonella_identity_and_voice(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "actions" / "screen_processor.py").read_text(encoding="utf-8")

        self.assertIn('cfg.get("assistant_name") or "Antonella"', source)
        self.assertIn('cfg.get("voice_name") or "Kore"', source)
        self.assertNotIn('"You are JARVIS', source)
        self.assertNotIn('voice_name="Charon"', source)

    # -.-.-.-
    def test_screen_capture_resolves_target_monitor_instead_of_forcing_primary(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "actions" / "screen_processor.py").read_text(encoding="utf-8")

        self.assertIn("select_monitor(monitors, point=point, hint=monitor_hint)", source)
        self.assertNotIn("monitors[1] if len(monitors) > 1 else monitors[0]", source)


if __name__ == "__main__":
    unittest.main()
