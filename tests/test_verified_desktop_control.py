import json
import unittest

from actions.verified_desktop_control import (
    _browser_name_from_process,
    _clamp_point,
    _json,
    _normalize_browser_name,
)


class VerifiedDesktopControlTests(unittest.TestCase):
    def test_browser_aliases_and_process_names_are_normalized(self):
        self.assertEqual(_normalize_browser_name("Google Chrome"), "chrome")
        self.assertEqual(_normalize_browser_name("Microsoft Edge"), "edge")
        self.assertEqual(_normalize_browser_name("Opera GX"), "operagx")
        self.assertEqual(_browser_name_from_process("chrome.exe"), "chrome")
        self.assertEqual(_browser_name_from_process("msedge.exe"), "edge")
        self.assertEqual(_browser_name_from_process("firefox.exe"), "firefox")
        self.assertEqual(_browser_name_from_process("notepad.exe"), "")

    def test_virtual_desktop_clamp_supports_negative_coordinates(self):
        bounds = (-1920, -200, 2559, 1439)
        self.assertEqual(_clamp_point(-2500, -500, bounds), (-1920, -200))
        self.assertEqual(_clamp_point(3000, 2000, bounds), (2559, 1439))
        self.assertEqual(_clamp_point(-800, 420, bounds), (-800, 420))

    def test_results_are_machine_readable_and_explicit_about_verification(self):
        rendered = _json(
            {
                "ok": False,
                "verified": False,
                "action": "browser_next_tab",
                "message": "Do not claim success.",
            }
        )
        payload = json.loads(rendered)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["verified"])
        self.assertEqual(payload["action"], "browser_next_tab")
        self.assertIn("Do not claim success", payload["message"])


if __name__ == "__main__":
    unittest.main()
