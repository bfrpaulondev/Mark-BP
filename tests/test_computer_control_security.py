import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch


pyautogui = types.ModuleType("pyautogui")
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05
pyperclip = types.ModuleType("pyperclip")
pyperclip.copy = Mock()
pyperclip.paste = Mock(return_value="")

with patch.dict(sys.modules, {"pyautogui": pyautogui, "pyperclip": pyperclip}):
    from actions import computer_control as computer_control_module


class ComputerControlSecurityTests(unittest.TestCase):
    def _win32_modules(self, titles):
        win32con = types.ModuleType("win32con")
        win32con.SW_RESTORE = 9

        win32gui = types.ModuleType("win32gui")
        win32gui.EnumWindows = lambda callback, extra: [
            callback(hwnd, extra) for hwnd in titles
        ]
        win32gui.IsWindowVisible = lambda hwnd: True
        win32gui.GetWindowText = lambda hwnd: titles[hwnd]
        win32gui.ShowWindow = Mock()
        win32gui.SetForegroundWindow = Mock()
        return win32con, win32gui

    def test_windows_focus_uses_win32_without_powershell(self):
        win32con, win32gui = self._win32_modules({10: "Notes", 20: "Google Chrome"})

        with patch.object(computer_control_module, "_get_os", return_value="windows"):
            with patch.object(computer_control_module.time, "sleep"):
                with patch.dict(sys.modules, {"win32con": win32con, "win32gui": win32gui}):
                    with patch.object(subprocess, "run") as run:
                        result = computer_control_module._focus_window("Chrome")

        self.assertEqual(result, "Focus requested for window: Chrome")
        win32gui.ShowWindow.assert_called_once_with(20, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow.assert_called_once_with(20)
        run.assert_not_called()

    def test_windows_focus_treats_command_text_as_literal_title(self):
        malicious = 'Chrome\"); Start-Process calc; #'
        win32con, win32gui = self._win32_modules({10: "Google Chrome"})

        with patch.object(computer_control_module, "_get_os", return_value="windows"):
            with patch.dict(sys.modules, {"win32con": win32con, "win32gui": win32gui}):
                with patch.object(subprocess, "run") as run:
                    result = computer_control_module._focus_window(malicious)

        self.assertIn("window not found", result)
        win32gui.SetForegroundWindow.assert_not_called()
        run.assert_not_called()

    def test_windows_focus_rejects_control_characters(self):
        with patch.object(computer_control_module, "_get_os", return_value="windows"):
            self.assertIn(
                "invalid window title",
                computer_control_module._focus_window("Chrome\nCalculator"),
            )


if __name__ == "__main__":
    unittest.main()
