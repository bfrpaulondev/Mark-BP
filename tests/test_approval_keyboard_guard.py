from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QWidget

    HAS_QT = True
except ImportError:  # pragma: no cover - dependency-free CI legs
    HAS_QT = False


class _RecordingSession:
    def __init__(self) -> None:
        self.approve_calls = 0
        self._status = {
            "state": "awaiting_approval",
            "last_action": "sensitive action",
            "history": [],
        }

    def status(self) -> dict:
        return dict(self._status)

    def approve_once(self) -> dict:
        self.approve_calls += 1
        return {"ok": True}

    def stop(self) -> dict:
        return {"ok": True}


class _HostLog:
    def append_event(self, text: str) -> None:
        pass


@unittest.skipUnless(HAS_QT, "PyQt6 unavailable: dependency-free CI legs skip")
class ApprovalKeyboardGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        from ui.agent_control import AgentControlDialog

        cls._dialog_cls = AgentControlDialog

    def setUp(self) -> None:
        self._host = QWidget()
        self._host._log = _HostLog()
        self.dialog = self._dialog_cls(self._host)
        self.session = _RecordingSession()
        self.dialog._session = self.session
        self.dialog.refresh()
        self.dialog.show()

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self._host.deleteLater()

    def test_enter_and_return_never_approve_even_when_button_has_focus(self) -> None:
        self.assertTrue(self.dialog._approve_button.isEnabled())
        self.dialog._approve_button.setFocus()

        QTest.keyClick(self.dialog._approve_button, Qt.Key.Key_Return)
        QTest.keyClick(self.dialog._approve_button, Qt.Key.Key_Enter)

        self.assertEqual(self.session.approve_calls, 0)

    def test_space_remains_explicit_keyboard_approval(self) -> None:
        self.assertTrue(self.dialog._approve_button.isEnabled())
        self.dialog._approve_button.setFocus()

        QTest.keyClick(self.dialog._approve_button, Qt.Key.Key_Space)

        self.assertEqual(self.session.approve_calls, 1)


if __name__ == "__main__":
    unittest.main()
