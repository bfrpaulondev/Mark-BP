import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


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
        self.assertIn("package_versions", data)
        self.assertIsInstance(data["package_versions"], dict)
        self.assertIn("monitor_count", data)
        self.assertFalse(data["cdp_available"] == "configured")

    def test_known_package_versions_never_return_paths(self):
        with mock.patch.object(
            probe_module.metadata,
            "version",
            side_effect=lambda name: "1.2.3" if name == "pywinauto" else (_ for _ in ()).throw(probe_module.metadata.PackageNotFoundError()),
        ):
            versions = probe_module._known_package_versions()
        self.assertEqual(versions, {"pywinauto": "1.2.3"})
        self.assertNotIn("/", json.dumps(versions))
        self.assertNotIn("\\", json.dumps(versions))

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

    def test_markdown_includes_bounded_error_detail(self):
        bundle = evidence_module.EvidenceBundle()
        bundle.add(
            evidence_module.EvidenceRecord(
                case_id="uia_inspect",
                status="FAIL",
                result={
                    "ok": False,
                    "delivered": False,
                    "verified": False,
                    "error_type": "AttributeError",
                    "error_detail": "wrapper has no attribute 'x'",
                },
            )
        )
        report = bundle.to_markdown()
        self.assertIn("Error detail", report)
        self.assertIn("wrapper has no attribute 'x'", report)


class RunnerDryRunTests(unittest.TestCase):
    def test_safe_error_detail_redacts_local_paths_and_bounds_output(self):
        fake_root = Path("C:/repo/Antonella")
        detail = runner_module._safe_error_detail(
            AttributeError(f"C:/repo/Antonella/file.py | missing\nattribute {'x' * 300}"),
            root=fake_root,
        )
        self.assertIn("<repo>", detail)
        self.assertNotIn("C:/repo/Antonella", detail)
        self.assertNotIn("|", detail)
        self.assertNotIn("\n", detail)
        self.assertLessEqual(len(detail), 180)

    def test_physical_exception_records_type_and_safe_detail(self):
        import tempfile

        original = runner_module.EXECUTORS.get("filesystem")
        runner_module.EXECUTORS["filesystem"] = lambda _cap: (_ for _ in ()).throw(
            AttributeError("synthetic missing attribute")
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with mock.patch.dict(
                    runner_module.os.environ,
                    {"ANTONELLA_E2E_PHYSICAL": "1"},
                    clear=False,
                ), mock.patch.object(runner_module.sys, "platform", "win32"):
                    bundle = runner_module.run(Path(tmp), capabilities={})
                record = {item.case_id: item for item in bundle.records}["filesystem"]
                self.assertEqual(record.status, "FAIL")
                self.assertEqual(record.result["error_type"], "AttributeError")
                self.assertEqual(record.result["error_detail"], "synthetic missing attribute")
        finally:
            if original is None:
                runner_module.EXECUTORS.pop("filesystem", None)
            else:
                runner_module.EXECUTORS["filesystem"] = original

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

    def test_missing_capabilities_are_only_not_available_on_physical_gate(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                runner_module.os.environ,
                {"ANTONELLA_E2E_PHYSICAL": "1"},
                clear=False,
            ), mock.patch.object(runner_module.sys, "platform", "win32"):
                bundle = runner_module.run(
                    Path(tmp),
                    capabilities={"pyqt6": False, "pywinauto": False},
                )
            by_id = {record.case_id: record for record in bundle.records}
            self.assertEqual(by_id["app_launch"].status, "NOT AVAILABLE")
            self.assertIn("pyqt6", by_id["app_launch"].environment["missing"])

    def test_monitor_count_requirement_comparison_on_physical_gate(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                runner_module.os.environ,
                {"ANTONELLA_E2E_PHYSICAL": "1"},
                clear=False,
            ), mock.patch.object(runner_module.sys, "platform", "win32"):
                bundle = runner_module.run(
                    Path(tmp),
                    capabilities={"monitor_count": 1},
                )
                by_id = {record.case_id: record for record in bundle.records}
                self.assertEqual(by_id["multi_monitor"].status, "NOT AVAILABLE")

                original = runner_module.EXECUTORS.get("multi_monitor")
                runner_module.EXECUTORS["multi_monitor"] = lambda capabilities: (
                    {"ok": True, "delivered": True, "verified": True},
                    {},
                )
                try:
                    bundle2 = runner_module.run(
                        Path(tmp),
                        capabilities={"monitor_count": 3},
                    )
                finally:
                    if original is None:
                        runner_module.EXECUTORS.pop("multi_monitor", None)
                    else:
                        runner_module.EXECUTORS["multi_monitor"] = original
                by_id2 = {record.case_id: record for record in bundle2.records}
                self.assertEqual(by_id2["multi_monitor"].status, "PASS")


if __name__ == "__main__":
    unittest.main()
