from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.windows_e2e import run_user_acceptance as acceptance


class WindowsUserAcceptanceTests(unittest.TestCase):
    def test_physical_gate_requires_windows_and_explicit_env(self):
        self.assertTrue(
            acceptance._physical_gate(
                {"ANTONELLA_E2E_PHYSICAL": "1"},
                "win32",
            )
        )
        self.assertFalse(acceptance._physical_gate({}, "win32"))
        self.assertFalse(
            acceptance._physical_gate(
                {"ANTONELLA_E2E_PHYSICAL": "1"},
                "linux",
            )
        )

    @patch("scripts.windows_e2e.run_user_acceptance.subprocess.Popen")
    def test_launch_antonella_uses_canonical_entrypoint_without_shell(self, popen):
        root = Path("C:/antonella")
        acceptance._launch_antonella(root)
        args, kwargs = popen.call_args
        self.assertEqual(args[0][0], acceptance.sys.executable)
        self.assertEqual(Path(args[0][1]), root / "antonella.py")
        self.assertEqual(Path(kwargs["cwd"]), root)
        self.assertNotIn("shell", kwargs)

    def test_voice_metrics_row_fails_closed_when_runtime_file_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(acceptance._voice_metrics_row(root)["status"], "FAIL")
            (root / "voice_metrics.json").write_text("{}", encoding="utf-8")
            self.assertEqual(acceptance._voice_metrics_row(root)["status"], "PASS")

    def test_stop_launched_terminates_process_and_waits(self):
        process = MagicMock()
        process.poll.return_value = None
        acceptance._stop_launched(process)
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=8)
        process.kill.assert_not_called()

    def test_acceptance_report_contains_only_status_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            out_dir = Path(temp)
            acceptance._write_acceptance(
                out_dir,
                [{"case_id": "voice-capture", "status": "PASS", "timestamp": 1.0}],
            )
            text = (out_dir / "user_acceptance.md").read_text(encoding="utf-8")
            self.assertIn("| voice-capture | PASS |", text)
            self.assertNotIn("timestamp", text)


if __name__ == "__main__":
    unittest.main()
