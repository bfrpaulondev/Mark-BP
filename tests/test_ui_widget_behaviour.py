"""ANT-270 behavioural widget tests (Qt offscreen).

Real widget tests over ``AgentControlDialog`` and ``AntonellaWindow``:
they require PyQt6 and are skipped on the dependency-free CI legs; they
run locally and in the dedicated ``ui-widget-tests`` CI job
(Windows + ``QT_QPA_PLATFORM=offscreen``).
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

    HAS_QT = True
except ImportError:  # pragma: no cover - dependency-free CI legs
    HAS_QT = False


def _status(**overrides) -> dict:
    payload = {
        "state": "idle",
        "objective": "",
        "target_window": "",
        "requested_monitor": None,
        "cost_mode": "economy",
        "provider": "",
        "model": "",
        "step": 0,
        "model_calls": 0,
        "visual_updates": 0,
        "batched_actions": 0,
        "saved_model_calls": 0,
        "capture_scope": "monitor",
        "capture_savings_pct": 0,
        "last_action": "",
        "last_error": "",
        "result": "",
        "awaiting_approval": False,
        "monitor_index": None,
        "history": [],
        "telemetry_task_id": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "estimated_cost_usd": None,
        "known_cost_usd": 0.0,
        "cost_complete": False,
    }
    payload.update(overrides)
    return payload


class _RecordingSession:
    def __init__(self):
        self.status_payload = _status()
        self.approve_calls = 0
        self.stop_calls = 0

    def status(self) -> dict:
        return dict(self.status_payload)

    def approve_once(self) -> dict:
        self.approve_calls += 1
        return {"ok": True}

    def stop(self) -> dict:
        self.stop_calls += 1
        return {"ok": True}


class _HostLog:
    def append_event(self, text: str) -> None:
        pass


class _FakeScreen:
    def __init__(self, rect: "QRect"):
        self._rect = QRect(rect)

    def availableGeometry(self) -> "QRect":
        return QRect(self._rect)


@unittest.skipUnless(HAS_QT, "PyQt6 unavailable: dependency-free CI legs skip")
class AgentControlWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        from ui.agent_control import AgentControlDialog

        cls._dialog_cls = AgentControlDialog

    def setUp(self):
        self._host = QWidget()
        self._host._log = _HostLog()
        self.dialog = self._dialog_cls(self._host)
        self.session = _RecordingSession()
        self.dialog._session = self.session
        self.dialog.show()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self._host.deleteLater()

    # -.-.-.-
    def test_dialog_constructs_without_exception(self):
        self.assertTrue(self.dialog.isVisible())

    def test_accessible_names_on_action_buttons(self):
        self.assertEqual(
            self.dialog._approve_button.accessibleName(),
            "Aprovar o passo pendente do agente",
        )
        self.assertEqual(self.dialog._stop_button.accessibleName(), "Parar o agente")

    def test_tab_order_is_approve_then_stop_then_close(self):
        after_approve = self.dialog._approve_button.nextInFocusChain()
        after_stop = self.dialog._stop_button.nextInFocusChain()
        self.assertIs(after_approve, self.dialog._stop_button)
        self.assertIsInstance(after_stop, QPushButton)
        self.assertEqual(after_stop.text(), "Fechar")

    def test_approve_button_is_never_default(self):
        self.assertFalse(self.dialog._approve_button.autoDefault())
        self.assertFalse(self.dialog._approve_button.isDefault())

    def test_enter_and_return_fail_closed_outside_approve_button(self):
        # Return with focus on the history view must never approve.
        self.dialog._history.setFocus()
        QTest.keyClick(self.dialog._history, Qt.Key.Key_Return)
        QTest.keyClick(self.dialog._history, Qt.Key.Key_Enter)
        # Dialog-level Return/Enter must never route to the approve action.
        QTest.keyClick(self.dialog, Qt.Key.Key_Return)
        QTest.keyClick(self.dialog, Qt.Key.Key_Enter)
        # Return on a different focused button must activate that button,
        # not the approval.
        self.dialog._details_toggle.setFocus()
        QTest.keyClick(self.dialog._details_toggle, Qt.Key.Key_Return)
        self.assertEqual(self.session.approve_calls, 0)

    def test_explicit_click_still_approves_only_when_enabled(self):
        # Idle: approval is disabled and even an explicit click must not fire.
        self.assertFalse(self.dialog._approve_button.isEnabled())
        self.dialog._approve_button.click()
        self.assertEqual(self.session.approve_calls, 0)
        # Awaiting approval: the explicit click is the only way through.
        self.session.status_payload = _status(state="awaiting_approval", last_action="delete_file")
        self.dialog.refresh()
        self.assertTrue(self.dialog._approve_button.isEnabled())
        self.dialog._approve_button.click()
        self.assertEqual(self.session.approve_calls, 1)

    def test_history_html_is_escaped_in_rendered_markup(self):
        self.session.status_payload = _status(
            state="executing",
            history=["click: <img src=x onerror=alert(1)> botão"],
        )
        self.dialog.refresh()
        rendered = self.dialog._history.toPlainText()
        self.assertIn("<img", rendered)  # entity-decoded back to text, never markup


@unittest.skipUnless(HAS_QT, "PyQt6 unavailable: dependency-free CI legs skip")
class MainWindowClampTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        from ui import AntonellaWindow

        cls._window_cls = AntonellaWindow

    def setUp(self):
        self.window = self._window_cls()
        self.window.resize(400, 300)
        self.window.show()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    # -.-.-.-
    def test_screen_hook_registered_on_show(self):
        self.assertTrue(getattr(self.window, "_screen_hooked", False))

    def test_clamp_moves_window_into_distant_screen(self):
        self.window._on_screen_changed(_FakeScreen(QRect(3000, 0, 1920, 1040)))
        self.assertTrue(QRect(3000, 0, 1920, 1040).contains(self.window.frameGeometry()))

    def test_window_larger_than_geometry_snaps_to_top_left(self):
        self.window.resize(2500, 1400)
        self.window._on_screen_changed(_FakeScreen(QRect(3000, 0, 1920, 1040)))
        self.assertEqual(self.window.x(), 3000)
        self.assertEqual(self.window.y(), 0)

    def test_negative_coordinate_screen_keeps_window_inside(self):
        self.window._on_screen_changed(_FakeScreen(QRect(-1920, -40, 1600, 900)))
        self.assertTrue(QRect(-1920, -40, 1600, 900).contains(self.window.frameGeometry()))

    def test_screen_none_is_a_noop(self):
        before = self.window.x()
        self.window._on_screen_changed(None)
        self.assertEqual(self.window.x(), before)

    def test_fully_visible_window_is_not_moved(self):
        screen = _FakeScreen(QRect(3000, 0, 1920, 1040))
        self.window._on_screen_changed(screen)
        placed = self.window.x()
        self.window._on_screen_changed(screen)
        self.assertEqual(self.window.x(), placed)


if __name__ == "__main__":
    unittest.main()
