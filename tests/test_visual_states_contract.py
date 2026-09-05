import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class VisualStatesContractTests(unittest.TestCase):
    """ANT-270 — deterministic offscreen screenshot infrastructure."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        import sys

        # Load the Qt-free runtime state module the same way the script does.
        spec = importlib.util.spec_from_file_location(
            "antonella_runtime_state_contract", ROOT / "ui" / "runtime_state.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls.ui_states = {state.value for state in module.UiState}

        script_path = ROOT / "scripts" / "ui_visual_states.py"
        cls.script_source = script_path.read_text(encoding="utf-8")
        spec2 = importlib.util.spec_from_file_location("antonella_visual_states", script_path)
        cls.script = importlib.util.module_from_spec(spec2)
        sys.modules[spec2.name] = cls.script
        spec2.loader.exec_module(cls.script)

    def test_window_states_cover_every_ui_state(self):
        self.assertEqual(set(self.script.WINDOW_STATES), self.ui_states)

    def test_dialog_cases_include_empty_error_and_approval(self):
        for case in ("empty", "awaiting_approval", "failed", "done"):
            self.assertIn(case, self.script.DIALOG_CASES)

    def test_script_never_persists_private_content(self):
        # The only writes are widget renders (grab().save); no text/file
        # writes exist, and dialog payloads are synthetic demo content.
        self.assertNotIn("open(", self.script_source)
        self.assertEqual(self.script_source.count(".save("), 1)
        self.assertIn("widget.grab().save", self.script_source)
        self.assertIn("demonstração", self.script_source)

    def test_script_pins_offscreen_platform_and_documents_limits(self):
        self.assertIn('QT_QPA_PLATFORM", "offscreen"', self.script_source)
        self.assertIn("NOT PHYSICAL WINDOWS E2E", self.script_source)


if __name__ == "__main__":
    unittest.main()
