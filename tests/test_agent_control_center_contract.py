import unittest
from pathlib import Path


class AgentControlCenterContractTests(unittest.TestCase):
    def test_agent_panel_exposes_local_safety_controls_and_telemetry(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "ui" / "agent_control.py").read_text(encoding="utf-8")

        for label in (
            "AGENTE DE COMPUTADOR",
            "PARAR AGENTE",
            "APROVAR 1 PASSO",
            "Chamadas IA",
            "Poupadas",
            "EXECUÇÃO RECENTE",
        ):
            self.assertIn(label, source)

        self.assertIn("approve_once", source)
        self.assertIn("self._session.stop()", source)
        self.assertIn("saved_model_calls", source)
        self.assertIn("requested_monitor", source)

    def test_runtime_hud_opens_agent_panel_without_model_tool_call(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "ui" / "runtime_dashboard.py").read_text(encoding="utf-8")

        self.assertIn("self._agent.clicked.connect(self._open_agent_control)", source)
        self.assertIn("show_agent_control", source)
        self.assertIn("Ctrl+Shift+A", source)
        self.assertIn("self._cost.clicked.connect(self._open_settings)", source)
        self.assertIn("self._expert.clicked.connect(self._open_settings)", source)


if __name__ == "__main__":
    unittest.main()
