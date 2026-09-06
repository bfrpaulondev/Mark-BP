from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ANTONELLA = ROOT / "antonella.py"


class LiveStartupCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ANTONELLA.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_antonella_forces_plain_v1beta_transport_path(self):
        init_method = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "__init__"
        )
        assignments = [node for node in ast.walk(init_method) if isinstance(node, ast.Assign)]
        self.assertTrue(
            any(
                any(
                    isinstance(target, ast.Attribute)
                    and target.attr == "_enhanced_live"
                    for target in assignment.targets
                )
                and isinstance(assignment.value, ast.Constant)
                and assignment.value.value is False
                for assignment in assignments
            )
        )

    def test_startup_watchdog_is_bounded_and_cancels_stalled_engine(self):
        run_method = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "run"
        )
        calls = [node for node in ast.walk(run_method) if isinstance(node, ast.Call)]
        self.assertTrue(
            any(
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "asyncio"
                and call.func.attr == "timeout"
                for call in calls
            )
        )
        self.assertTrue(
            any(
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "cancel"
                for call in calls
            )
        )
        self.assertIn("LIVE_STARTUP_TIMEOUT_SECONDS = 20.0", self.source)

    def test_timeout_path_surfaces_visible_failure_reason(self):
        self.assertIn("Live session startup timed out", self.source)
        self.assertIn('self.ui.set_state("FAILED")', self.source)


if __name__ == "__main__":
    unittest.main()
