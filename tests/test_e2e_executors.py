import tempfile
import time
import unittest
from pathlib import Path

from scripts.windows_e2e import matrix as e2e_matrix
from scripts.windows_e2e.executors import EXECUTORS, _exec_filesystem
from scripts.windows_e2e.run_physical import SkipCase, run


class ExecutorRegistryTests(unittest.TestCase):
    def test_registered_executors_match_matrix_cases(self):
        for case_id in EXECUTORS:
            with self.subTest(case=case_id):
                self.assertIsNotNone(e2e_matrix.get_case(case_id))

    def test_expected_physical_cases_are_registered(self):
        expected = {
            "filesystem", "app_launch", "window_focus", "uia_inspect", "uia_click",
            "uia_set_text", "mouse_move", "mouse_click", "keyboard", "volume", "mute",
            "brightness", "wifi", "browser_tabs", "spa", "popup", "download",
            "multi_monitor", "dpi",
        }
        self.assertTrue(expected.issubset(EXECUTORS))

    def test_unsafe_or_hardware_cases_stay_unregistered(self):
        # Honest SKIPPED: these need runtime instrumentation or hardware
        # scenarios that cannot be simulated safely.
        for case_id in ("voice", "barge_in", "computer_use_pause", "target_disappeared", "hot_plug"):
            self.assertNotIn(case_id, EXECUTORS)


class FilesystemExecutorTests(unittest.TestCase):
    def test_filesystem_executor_verifies_round_trip(self):
        result, evidence = _exec_filesystem({})
        self.assertTrue(result["ok"])
        self.assertTrue(result["delivered"])
        self.assertTrue(result["verified"])
        self.assertTrue(evidence["hash"])

    def test_filesystem_executor_output_is_synthetic(self):
        import hashlib

        result, evidence = _exec_filesystem({})
        self.assertEqual(
            evidence["hash"],
            hashlib.sha256("antonella synthetic".encode("utf-8")).hexdigest()[:16],
        )


class RunnerSkipCaseTests(unittest.TestCase):
    def test_skip_case_is_reported_as_skipped_never_pass(self):
        import sys as real_sys
        import types

        with tempfile.TemporaryDirectory() as tmp:
            original_executors = dict(run.__globals__["EXECUTORS"])
            original_sys = run.__globals__["sys"]
            # Only the case under test is registered with the gate on —
            # otherwise every physical executor would run in the suite.
            run.__globals__["EXECUTORS"] = {
                "filesystem": lambda caps: (_ for _ in ()).throw(SkipCase("no sandbox available")),
            }
            # Fake a physical Windows gate deterministically on any platform.
            run.__globals__["sys"] = types.SimpleNamespace(platform="win32")
            run.__globals__["os"].environ["ANTONELLA_E2E_PHYSICAL"] = "1"
            try:
                bundle = run(Path(tmp), capabilities={"pyqt6": True, "pywinauto": True})
            finally:
                run.__globals__["EXECUTORS"] = original_executors
                run.__globals__["sys"] = original_sys
                run.__globals__["os"].environ.pop("ANTONELLA_E2E_PHYSICAL", None)
            by_id = {record.case_id: record for record in bundle.records}
            self.assertEqual(by_id["filesystem"].status, "SKIPPED")
            report = (Path(tmp) / "report.md").read_text(encoding="utf-8")
            self.assertIn("| filesystem | SKIPPED |", report)
            self.assertNotIn("| filesystem | PASS |", report)


if __name__ == "__main__":
    unittest.main()
