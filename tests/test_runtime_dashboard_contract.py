import unittest
from pathlib import Path


class RuntimeDashboardContractTests(unittest.TestCase):
    def test_dashboard_keeps_reference_ui_and_exposes_runtime_status(self):
        root = Path(__file__).resolve().parent.parent
        dashboard = (root / "ui" / "runtime_dashboard.py").read_text(encoding="utf-8")
        entrypoint = (root / "antonella.py").read_text(encoding="utf-8")

        for label in ("Live", "Especialista", "Custo", "Visão", "Agente"):
            self.assertIn(label, dashboard)

        self.assertIn("Ctrl+K", dashboard)
        self.assertIn("attach_runtime_dashboard", entrypoint)
        self.assertIn("build_runtime_snapshot", dashboard)

    def test_dashboard_does_not_render_secret_values(self):
        root = Path(__file__).resolve().parent.parent
        dashboard = (root / "ui" / "runtime_dashboard.py").read_text(encoding="utf-8")

        self.assertNotIn("openai_api_key]", dashboard)
        self.assertNotIn("gemini_api_key]", dashboard)


if __name__ == "__main__":
    unittest.main()
