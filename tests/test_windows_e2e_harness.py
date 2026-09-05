import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_module = _load("e2e_capability_probe", "scripts/windows_e2e/capability_probe.py")
matrix_module = _load("e2e_matrix", "scripts/windows_e2e/matrix.py")
evidence_module = _load("e2e_evidence", "scripts/windows_e2e/evidence.py")
runner_module = _load("e2e_runner", "scripts/windows_e2e/run_physical.py")

REQUIRED_BASELINE = {
    "app_launch", "window_focus", "uia_inspect", "uia_click", "uia_set_text",
    "mouse_move", "mouse_click", "keyboard", "filesystem", "volume", "mute",
    "brightness", "wifi", "browser_tabs", "spa", "popup", "download",
    "computer_use_pause", "computer_use_resume", "computer_use_stop",
    "multi_monitor", "dpi", "hot_plug", "stale_frame", "voice", "barge_in",
}

REQUIRED_FAILURE_SCENARIOS = {
    "target_disappeared", "target_moved", "target_minimized", "window_recreated",
    "screen_changed", "approval_delayed", "frame_stale", "scroll_retry",
    "click_no_retry", "type_no_retry", "hotkey_no_retry", "stop_during_wait",
    "stop_during_recovery",
}


class MatrixDefinitionTests(unittest.TestCase):
    def test_c3_baseline_cases_are_all_defined(self):
        self.assertTrue(REQUIRED_BASELINE.issubset(matrix_module.CASE_IDS))

    def test_c9_failure_scenarios_are_all_defined(self):
        self.assertTrue(REQUIRED_FAILURE_SCENARIOS.issubset(matrix_module.CASE_IDS))

    def test_cases_have_descriptions_and_known_risk(self):
        for case in matrix_module.CASES:
            with self.subTest(case=case.case_id):
                self.assertTrue(case.description.strip())
                self.assertIn(case.category, {
                    "ui", "uia", "mouse", "keyboard", "filesystem", "audio",
                    "system", "browser", "computer_use", "multi_monitor",
                    "voice", "computer_use_failure",
                })
                self.assertIn(case.risk, ("safe", "medium", "dangerous"))


class CapabilityProbeTests(unittest.TestCase):
    def test_probe_runs_on_any_platform_without_pii(self):
        data = probe_module.probe()
        text = json.dumps(data).lower()
        for forbidden in ("users\\\\", "userprofile", "home)", "bruno", "desktop"):
            self.assertNotIn(forbidden, text)
        self.assertIn("python_version", data)
        self.assertIn("monitor_count", data)
        self.assertFalse(data["cdp_available"] == "configured")

    def test_monitor_requirements_use_probe_keys(self):
        known_keys = set(probe_module.probe()) | {"monitor_count>=2", "chrome_available"}
        for case in matrix_module.CASES:
            for requirement in case.requirements:
                base = requirement.split(">=")[0].strip()
                with self.subTest(case=case.case_id, requirement=requirement):
                    self.assertIn(base, known_keys)


class EvidenceBundleTests(unittest.TestCase):
    def test_status_vocabulary_is_closed(self):
        with self.assertRaises(ValueError):
            evidence_module.EvidenceRecord(case_id="x", status="pass")

    def test_evidence_is_sanitised_and_bounded(self):
        record = evidence_module.EvidenceRecord(
            case_id="uia_click",
            status="PASS",
            result={"ok": True, "delivered": True, "verified": True, "screenshot": "secret.png"},
            evidence={"hash": "abc", "password": "hunter2", "transcript": "private", "count": 3},
        )
        self.assertNotIn("password", record.evidence)
        self.assertNotIn("transcript", record.evidence)
        self.assertNotIn("screenshot", record.result)
        self.assertEqual(record.evidence["count"], 3)

    def test_markdown_never_converts_skipped_into_pass(self):
        bundle = evidence_module.EvidenceBundle()
        bundle.add(evidence_module.EvidenceRecord(case_id="voice", status="SKIPPED"))
        bundle.add(evidence_module.EvidenceRecord(case_id="dpi", status="NOT PHYSICALLY TESTED"))
        report = bundle.to_markdown()
        self.assertIn("| voice | SKIPPED |", report)
        self.assertIn("| dpi | NOT PHYSICALLY TESTED |", report)
        self.assertIn("never counted as PASS", report)


class RunnerDryRunTests(unittest.TestCase):
    def test_dry_run_marks_everything_not_physically_tested(self):
        import tempfile

        full_capabilities = {key: True for key in probe_module.probe()}
        full_capabilities["monitor_count"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            bundle = runner_module.run(Path(tmp), capabilities=full_capabilities)
            statuses = {record.status for record in bundle.records}
            self.assertEqual(statuses, {"NOT PHYSICALLY TESTED"})
            self.assertEqual(len(bundle.records), len(matrix_module.CASES))
            report = (Path(tmp) / "report.md").read_text(encoding="utf-8")
            self.assertIn("NOT PHYSICALLY TESTED", report)

    def test_missing_capabilities_mark_case_not_available(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bundle = runner_module.run(Path(tmp), capabilities={"pyqt6": False})
            by_id = {record.case_id: record for record in bundle.records}
            self.assertEqual(by_id["app_launch"].status, "NOT AVAILABLE")
            self.assertIn("pyqt6", by_id["app_launch"].environment["missing"])

    def test_monitor_count_requirement_comparison(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bundle = runner_module.run(Path(tmp), capabilities={"monitor_count": 1})
            by_id = {record.case_id: record for record in bundle.records}
            self.assertEqual(by_id["multi_monitor"].status, "NOT AVAILABLE")
            bundle2 = runner_module.run(Path(tmp), capabilities={"monitor_count": 3})
            by_id2 = {record.case_id: record for record in bundle2.records}
            self.assertEqual(by_id2["multi_monitor"].status, "NOT PHYSICALLY TESTED")


if __name__ == "__main__":
    unittest.main()
