import importlib.util
import sys
import unittest
from pathlib import Path

# CI runs isolated unit tests without PyQt6, so load runtime_state.py from
# its file instead of importing the ui package (whose __init__ pulls in Qt).
_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "antonella_runtime_state", _ROOT / "ui" / "runtime_state.py"
)
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module  # required by dataclass string annotations
_spec.loader.exec_module(_module)

STATE_LABELS_PT = _module.STATE_LABELS_PT
UiRuntimeState = _module.UiRuntimeState
UiState = _module.UiState
normalize_state = _module.normalize_state
state_label_pt = _module.state_label_pt


class NormalizeStateTests(unittest.TestCase):
    def test_canonical_states_pass_through(self):
        for state in UiState:
            self.assertIs(normalize_state(state), state)
            self.assertIs(normalize_state(state.value), state)

    def test_case_and_whitespace_insensitive(self):
        self.assertIs(normalize_state("  listening "), UiState.LISTENING)
        self.assertIs(normalize_state("waiting_approval"), UiState.WAITING_APPROVAL)

    def test_legacy_engine_strings_map_to_canonical_states(self):
        self.assertIs(normalize_state("PROCESSING"), UiState.EXECUTING)
        self.assertIs(normalize_state("READY"), UiState.IDLE)
        self.assertIs(normalize_state("STANDBY"), UiState.IDLE)
        self.assertIs(normalize_state("AWAITING_APPROVAL"), UiState.WAITING_APPROVAL)
        self.assertIs(normalize_state("PENDING_APPROVAL"), UiState.WAITING_APPROVAL)
        self.assertIs(normalize_state("ERROR"), UiState.FAILED)
        self.assertIs(normalize_state("ABORTED"), UiState.CANCELLED)

    def test_legacy_members_are_preserved(self):
        # SPEAKING / SLEEPING / MUTED / INITIALISING keep working unchanged.
        self.assertIs(normalize_state("SPEAKING"), UiState.SPEAKING)
        self.assertIs(normalize_state("SLEEPING"), UiState.SLEEPING)
        self.assertIs(normalize_state("MUTED"), UiState.MUTED)
        self.assertIs(normalize_state("INITIALISING"), UiState.INITIALISING)

    def test_unknown_and_empty_values_do_not_claim_ready(self):
        self.assertIs(normalize_state(None), UiState.UNKNOWN)
        self.assertIs(normalize_state(""), UiState.UNKNOWN)
        self.assertIs(normalize_state("   "), UiState.UNKNOWN)
        self.assertIs(normalize_state("GARBAGE_STATE"), UiState.UNKNOWN)
        self.assertIs(normalize_state(123), UiState.UNKNOWN)
        self.assertNotEqual(normalize_state("GARBAGE_STATE"), UiState.IDLE)


class StateLabelTests(unittest.TestCase):
    def test_every_state_has_a_pt_label(self):
        self.assertEqual(set(STATE_LABELS_PT), set(UiState))
        for state in UiState:
            label = state_label_pt(state)
            self.assertTrue(label, f"missing label for {state}")
            self.assertEqual(label, label.upper())

    def test_canonical_labels_follow_ant_268_vocabulary(self):
        self.assertEqual(state_label_pt(UiState.IDLE), "PRONTA")
        self.assertEqual(state_label_pt(UiState.LISTENING), "A OUVIR")
        self.assertEqual(state_label_pt(UiState.THINKING), "A PENSAR")
        self.assertEqual(state_label_pt(UiState.OBSERVING), "A OBSERVAR")
        self.assertEqual(state_label_pt(UiState.EXECUTING), "A EXECUTAR")
        self.assertEqual(state_label_pt(UiState.VERIFYING), "A VERIFICAR")
        self.assertEqual(state_label_pt(UiState.RECOVERING), "A RECUPERAR")
        self.assertEqual(state_label_pt(UiState.WAITING_APPROVAL), "A AGUARDAR APROVAÇÃO")
        self.assertEqual(state_label_pt(UiState.COMPLETED), "CONCLUÍDO")
        self.assertEqual(state_label_pt(UiState.FAILED), "FALHOU")
        self.assertEqual(state_label_pt(UiState.CANCELLED), "CANCELADO")
        self.assertEqual(state_label_pt(UiState.UNKNOWN), "ESTADO INDISPONÍVEL")


class UiRuntimeStateTests(unittest.TestCase):
    def test_defaults(self):
        snapshot = UiRuntimeState()
        self.assertIs(snapshot.state, UiState.IDLE)
        self.assertIsNone(snapshot.progress)
        self.assertIsNone(snapshot.error)

    def test_progress_is_clamped(self):
        self.assertEqual(UiRuntimeState(progress=150).progress, 100)
        self.assertEqual(UiRuntimeState(progress=-5).progress, 0)
        self.assertEqual(UiRuntimeState(progress=42).progress, 42)

    def test_state_is_normalized_on_construction(self):
        self.assertIs(UiRuntimeState(state="processing").state, UiState.EXECUTING)
        self.assertIs(UiRuntimeState(state="nonsense").state, UiState.UNKNOWN)

    def test_with_state_returns_moved_copy(self):
        base = UiRuntimeState(task_id="T1", task_name="Exportar")
        moved = base.with_state(UiState.EXECUTING)
        self.assertIs(moved.state, UiState.EXECUTING)
        self.assertEqual(moved.task_id, "T1")
        self.assertIs(base.state, UiState.IDLE)

    def test_to_dict_is_technical_metadata_only(self):
        allowed = {
            "state",
            "task_id",
            "task_name",
            "progress",
            "current_step",
            "tool",
            "provider",
            "model",
            "target_window",
            "target_monitor",
            "verified",
            "error",
            "approval",
            "model_calls",
            "calls_saved",
            "estimated_cost",
            "elapsed",
        }
        payload = UiRuntimeState(state=UiState.FAILED, error="x").to_dict()
        self.assertEqual(set(payload), allowed)
        self.assertEqual(payload["state"], "FAILED")

    def test_snapshot_never_caries_secret_fields(self):
        forbidden = ("api_key", "password", "token", "clipboard", "screenshot", "cookie", "prompt")
        fields = set(UiRuntimeState.__dataclass_fields__)
        for word in forbidden:
            self.assertNotIn(word, fields, f"secret-carrying field {word} must not exist")


class UiBindingContractTests(unittest.TestCase):
    """Repo-convention contract tests over the widget binding source."""

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.window = (root / "ui" / "__init__.py").read_text(encoding="utf-8")
        cls.dashboard = (root / "ui" / "runtime_dashboard.py").read_text(encoding="utf-8")

    def test_window_exposes_structured_state_signal_and_binding(self):
        self.assertIn("_runtime_state_signal = pyqtSignal(object)", self.window)
        self.assertIn("self._runtime_state_signal.connect(self._apply_runtime_state)", self.window)
        self.assertIn("def _apply_runtime_state", self.window)

    def test_legacy_string_entry_point_normalizes_instead_of_infering(self):
        self.assertIn("def _apply_state(self, state: str) -> None:", self.window)
        self.assertIn("UiRuntimeState(state=normalize_state(state))", self.window)

    def test_shim_exposes_set_runtime_state(self):
        self.assertIn("def set_runtime_state", self.window)

    def test_orb_consumes_central_labels_not_local_strings(self):
        self.assertIn("STATE_LABELS_PT.get(self.state", self.window)

    def test_dashboard_understands_normalized_executing_state(self):
        self.assertIn('"EXECUTING", "VERIFYING", "RECOVERING"', self.dashboard)


if __name__ == "__main__":
    unittest.main()
