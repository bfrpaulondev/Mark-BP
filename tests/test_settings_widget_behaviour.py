from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

    HAS_QT = True
except ImportError:  # pragma: no cover - dependency-free CI legs
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PyQt6 unavailable: dependency-free CI legs skip")
class SettingsDialogBehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        import ui.settings_dialog as settings_module

        cls._settings_module = settings_module
        cls._dialog_cls = settings_module.AntonellaSettingsDialog

    def setUp(self) -> None:
        self.applied: list[dict] = []
        self._original_apply = self._settings_module.apply_session_preferences
        self._settings_module.apply_session_preferences = lambda **kwargs: (
            self.applied.append(kwargs),
            {"changed": [], "restart_required": []},
        )[1]
        self._host = QWidget()
        self.dialog = self._dialog_cls(self._host)
        self.dialog.show()
        self._app.processEvents()

    def tearDown(self) -> None:
        self._settings_module.apply_session_preferences = self._original_apply
        self.dialog.close()
        self.dialog.deleteLater()
        self._host.deleteLater()
        self._app.processEvents()

    # -.-.-.-
    def _buttons(self) -> dict[str, QPushButton]:
        return {button.text(): button for button in self.dialog.findChildren(QPushButton)}

    def test_constructs_with_accessible_non_default_commit(self) -> None:
        buttons = self._buttons()
        cancel = buttons["Cancelar"]
        apply_button = buttons["Aplicar"]
        self.assertTrue(self.dialog.isVisible())
        self.assertFalse(cancel.autoDefault())
        self.assertFalse(cancel.isDefault())
        self.assertFalse(apply_button.autoDefault())
        self.assertFalse(apply_button.isDefault())
        self.assertEqual(cancel.accessibleName(), "Cancelar alterações")
        self.assertEqual(apply_button.accessibleName(), "Aplicar preferências")
        self.assertIs(cancel.nextInFocusChain(), apply_button)

    def test_enter_return_never_apply_at_dialog_level(self) -> None:
        QTest.keyClick(self.dialog, Qt.Key.Key_Return)
        QTest.keyClick(self.dialog, Qt.Key.Key_Enter)
        self.assertEqual(self.applied, [])

    def test_focused_apply_consumes_enter_return_but_space_commits(self) -> None:
        apply_button = self._buttons()["Aplicar"]
        apply_button.setFocus()
        self._app.processEvents()

        QTest.keyClick(apply_button, Qt.Key.Key_Return)
        QTest.keyClick(apply_button, Qt.Key.Key_Enter)
        self.assertEqual(self.applied, [])

        QTest.keyClick(apply_button, Qt.Key.Key_Space)
        self.assertEqual(len(self.applied), 1)

    def test_explicit_click_commits_once(self) -> None:
        self._buttons()["Aplicar"].click()
        self.assertEqual(len(self.applied), 1)


if __name__ == "__main__":
    unittest.main()
