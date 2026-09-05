import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class WindowsUiHardeningTests(unittest.TestCase):
    """ANT-270 (slice 1) — focus, accessibility and multi-monitor clamping.

    Source-level contracts; the behavioural counterpart lives in
    ``tests/test_ui_widget_behaviour.py`` (real Qt widgets, offscreen).
    """

    @classmethod
    def setUpClass(cls):
        cls.window = (ROOT / "ui" / "__init__.py").read_text(encoding="utf-8")
        cls.panel = (ROOT / "ui" / "agent_control.py").read_text(encoding="utf-8")

    def test_icon_only_buttons_have_accessible_names(self):
        for name in (
            "setAccessibleName(\"Abrir definições\")",
            "setAccessibleName(\"Interromper resposta\")",
            "setAccessibleName(\"Pausar ou retomar microfone\")",
        ):
            self.assertIn(name, self.window)

    def test_buttons_have_visible_focus_styles(self):
        self.assertGreaterEqual(self.window.count("QPushButton:focus"), 2)
        self.assertGreaterEqual(self.panel.count("QPushButton:focus"), 3)

    def test_command_bar_tab_order_follows_visual_row(self):
        self.assertIn("QWidget.setTabOrder(self._input, self._interrupt_button)", self.window)
        self.assertIn("QWidget.setTabOrder(self._interrupt_button, self._mic_button)", self.window)

    def test_window_clamps_back_into_view_on_screen_change(self):
        self.assertIn("screenChanged.connect(self._on_screen_changed)", self.window)
        self.assertIn("geo.contains(frame)", self.window)
        self.assertIn("geo.right() - frame.width()", self.window)
        self.assertIn("geo.bottom() - frame.height()", self.window)

    def test_agent_panel_tab_order_is_approve_then_stop_then_close(self):
        self.assertIn("QWidget.setTabOrder(self._approve_button, self._stop_button)", self.panel)
        self.assertIn("QWidget.setTabOrder(self._stop_button, close_button)", self.panel)

    def test_agent_panel_buttons_have_accessible_names(self):
        for name in ("Aprovar o passo pendente", "Parar o agente", "Fechar painel do agente"):
            self.assertIn(name, self.panel)

    def test_approval_never_fires_from_keyboard_default(self):
        # A QDialog promotes plain QPushButtons to auto-default Return
        # targets; approval must be excluded explicitly.
        self.assertIn("setAutoDefault(False)", self.panel)
        self.assertIn("setDefault(False)", self.panel)
        self.assertNotIn("returnPressed", self.panel)

    def test_panel_constants_are_self_consistent(self):
        # Every module-level constant used must be defined in the module
        # (regression guard for the _BORDER_HOVER bug).
        import re

        defined = set(re.findall(r"^_([A-Z][A-Z0-9_]*) =", self.panel, flags=re.M))
        used = set(re.findall(r"\b_([A-Z][A-Z0-9_]*)\b", self.panel))
        missing = {f"_{name}" for name in used if name not in defined}
        self.assertEqual(missing, set(), f"undefined module constants: {missing}")


if __name__ == "__main__":
    unittest.main()
