import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _status_keys_from_contracts() -> set[str]:
    """Extract the keys published by SessionState.as_dict() in the core."""
    contracts = (ROOT / "core" / "computer_use" / "contracts.py").read_text(encoding="utf-8")
    block = contracts.split("def as_dict", 1)[1]
    block = block.split("def _optional_int", 1)[0]
    return set(re.findall(r'"(\w+)":', block))


class AgentControlEvolutionTests(unittest.TestCase):
    """ANT-269 — Agent Control Center consumes only published session fields."""

    @classmethod
    def setUpClass(cls):
        cls.panel = (ROOT / "ui" / "agent_control.py").read_text(encoding="utf-8")

    def test_panel_only_reads_fields_published_by_session_state(self):
        used = set(re.findall(r'status\.get\("(\w+)"', self.panel))
        published = _status_keys_from_contracts()
        self.assertTrue(used, "panel must read at least one status field")
        self.assertEqual(used - published, set(), f"unknown status keys: {used - published}")

    def test_progress_is_honest_and_never_fabricates_a_total(self):
        self.assertIn("setTextVisible(False)", self.panel)
        self.assertIn("setRange(0, 0)", self.panel)
        self.assertNotRegex(self.panel, r"setValue\(int\(.*step.*\)\s*\*\s*100")

    def test_cost_uses_only_published_ant264_telemetry_or_mode(self):
        for field in (
            "cost_mode",
            "estimated_cost_usd",
            "known_cost_usd",
            "cost_complete",
        ):
            self.assertIn(f'status.get("{field}")', self.panel)
        self.assertIn('"quality": "Qualidade"', self.panel)
        self.assertNotIn('"premium": "Premium"', self.panel)
        self.assertIn("≥ US$", self.panel)
        self.assertIn("· parcial", self.panel)

    def test_target_window_is_displayed(self):
        self.assertIn("Janela alvo", self.panel)
        self.assertIn('status.get("target_window")', self.panel)

    def test_technical_evidence_is_progressively_disclosed(self):
        self.assertIn('self._details_row.setVisible(False)', self.panel)
        self.assertIn("_toggle_details", self.panel)
        for field in ("capture_scope", "capture_savings_pct", "visual_updates", "batched_actions"):
            self.assertIn(field, self.panel)

    def test_approval_is_contextual_and_enter_is_never_bound(self):
        self.assertIn('APROVAR: {pending[:38]}', self.panel)
        self.assertNotIn("returnPressed", self.panel)

    def test_history_uses_full_html_escape_before_rendering(self):
        self.assertIn("html.escape(str(line), quote=False)", self.panel)
        self.assertNotIn('replace("<", "&lt;")', self.panel)


if __name__ == "__main__":
    unittest.main()
