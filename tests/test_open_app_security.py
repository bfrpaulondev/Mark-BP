import importlib
import subprocess
import unittest
from unittest.mock import patch


open_app_module = importlib.import_module("actions.open_app")


class OpenAppSecurityTests(unittest.TestCase):
    def test_only_known_windows_uri_scheme_is_allowed(self):
        self.assertTrue(open_app_module._is_allowed_windows_uri("ms-settings:"))
        self.assertTrue(open_app_module._is_allowed_windows_uri("ms-settings:display"))
        self.assertFalse(open_app_module._is_allowed_windows_uri("C:\\Windows\\System32\\cmd.exe"))
        self.assertFalse(open_app_module._is_allowed_windows_uri("https://example.com"))

    @patch("actions.open_app.time.sleep")
    @patch("actions.open_app.subprocess.Popen")
    @patch("actions.open_app.shutil.which", return_value=r"C:\\Windows\\notepad.exe")
    def test_windows_executable_launch_never_uses_shell(self, _which, popen, _sleep):
        self.assertTrue(open_app_module._launch_windows("notepad.exe"))

        popen.assert_called_once_with(
            [r"C:\\Windows\\notepad.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_open_app_rejects_control_characters(self):
        result = open_app_module.open_app({"app_name": "notepad\ncalc"})

        self.assertEqual(result, "Invalid application name.")


if __name__ == "__main__":
    unittest.main()
