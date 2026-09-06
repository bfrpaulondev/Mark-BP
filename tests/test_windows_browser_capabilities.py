from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from scripts.windows_e2e import capability_probe
from scripts.windows_e2e import run_user_acceptance as acceptance


class WindowsBrowserCapabilityTests(unittest.TestCase):
    def test_browser_candidates_include_brave_and_chromium(self):
        candidates = capability_probe._browser_candidates()
        self.assertIn("brave", candidates)
        self.assertIn("chromium", candidates)
        self.assertIn("chrome", candidates)
        self.assertIn("edge", candidates)

    def test_browser_available_reports_install_presence_without_preference_claim(self):
        original_exists = Path.exists

        def fake_exists(path: Path) -> bool:
            value = str(path).replace("\\", "/")
            if "BraveSoftware/Brave-Browser/Application/brave.exe" in value:
                return True
            return original_exists(path)

        with mock.patch.object(capability_probe.sys, "platform", "win32"), mock.patch.dict(
            capability_probe.os.environ,
            {"ProgramFiles": "C:/Program Files", "LOCALAPPDATA": "C:/Local"},
            clear=False,
        ), mock.patch.object(Path, "exists", fake_exists):
            self.assertTrue(capability_probe._browser_available("brave"))

    def test_probe_exposes_browser_map_engine_and_optional_dependency_map(self):
        with mock.patch.object(capability_probe, "_windows_monitors", return_value=[]), mock.patch.object(
            capability_probe,
            "_browser_availability",
            return_value={"brave": True, "chromium": True, "chrome": False, "edge": False},
        ), mock.patch.object(
            capability_probe,
            "_module_available",
            side_effect=lambda name: name in {"pywinauto", "PyQt6"},
        ), mock.patch.object(
            capability_probe,
            "_known_package_versions",
            return_value={},
        ), mock.patch.object(
            capability_probe,
            "_microphone_available",
            return_value=False,
        ):
            data = capability_probe.probe()

        self.assertEqual(
            data["browsers_available"],
            {"brave": True, "chromium": True, "chrome": False, "edge": False},
        )
        self.assertTrue(data["brave_available"])
        self.assertTrue(data["chromium_available"])
        self.assertEqual(data["browser_test_engine"], "playwright-chromium")
        self.assertTrue(data["optional_dependencies"]["pywinauto"])
        self.assertTrue(data["optional_dependencies"]["pyqt6"])
        self.assertEqual(data["pywinauto"], data["optional_dependencies"]["pywinauto"])

    def test_acceptance_summaries_are_honest(self):
        capabilities = {
            "browsers_available": {
                "brave": True,
                "chromium": True,
                "chrome": False,
                "edge": False,
            },
            "optional_dependencies": {
                "pywinauto": True,
                "pycaw": False,
                "playwright": True,
            },
        }
        self.assertEqual(
            acceptance._browser_capability_summary(capabilities),
            "brave, chromium",
        )
        self.assertEqual(
            acceptance._optional_dependency_summary(capabilities),
            "pywinauto, playwright",
        )


if __name__ == "__main__":
    unittest.main()
