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

    def _method(self, name: str):
        return next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        )

    def test_antonella_forces_plain_v1beta_transport_path(self):
        init_method = self._method("__init__")
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
        run_method = self._method("run")
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

    def test_microphone_uplink_uses_explicit_audio_blob(self):
        send_method = self._method("_send_realtime")
        calls = [node for node in ast.walk(send_method) if isinstance(node, ast.Call)]
        live_calls = [
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "send_realtime_input"
        ]
        self.assertTrue(live_calls)
        self.assertTrue(
            any(any(keyword.arg == "audio" for keyword in call.keywords) for call in live_calls)
        )
        self.assertFalse(
            any(any(keyword.arg == "media" for keyword in call.keywords) for call in live_calls)
        )
        self.assertIn('mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}"', self.source)

    def test_interactive_text_uses_realtime_text_channel(self):
        schedule_method = self._method("_schedule_realtime_text")
        calls = [node for node in ast.walk(schedule_method) if isinstance(node, ast.Call)]
        live_calls = [
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "send_realtime_input"
        ]
        self.assertTrue(live_calls)
        self.assertTrue(
            any(any(keyword.arg == "text" for keyword in call.keywords) for call in live_calls)
        )
        text_method = self._method("_on_text_command")
        text_source = ast.unparse(text_method)
        self.assertIn("_schedule_realtime_text(text, label='text input')", text_source)
        self.assertNotIn("super()._on_text_command", text_source)

    def test_background_send_failures_are_not_silent(self):
        report_method = self._method("_report_live_send_failure")
        report_source = ast.unparse(report_method)
        self.assertIn("future.result()", report_source)
        self.assertIn("ERR: Live", report_source)
        self.assertIn("FAILED", report_source)


if __name__ == "__main__":
    unittest.main()
