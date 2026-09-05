import importlib.util
import unittest
from pathlib import Path


class WindowsCIContractTests(unittest.TestCase):
    """ANT-273 — Windows CI must keep baseline parity and the import smoke."""

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.root = root
        cls.workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        cls.smoke = (root / "scripts" / "ci_import_smoke.py").read_text(encoding="utf-8")
        spec = importlib.util.spec_from_file_location(
            "antonella_ci_import_smoke",
            root / "scripts" / "ci_import_smoke.py",
        )
        cls.smoke_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.smoke_module)

    def test_windows_baseline_job_exists_for_both_versions(self):
        self.assertIn("windows-baseline:", self.workflow)
        self.assertIn("windows-latest", self.workflow)
        self.assertIn('- "3.11"', self.workflow)
        self.assertIn('- "3.12"', self.workflow)

    def test_windows_job_matches_isolated_baseline_steps(self):
        windows_block = self.workflow.split("windows-baseline:", 1)[1]
        for step in (
            "Install settings test dependency",
            "Compile Python sources",
            "Run isolated unit tests",
        ):
            self.assertIn(step, windows_block)

    def test_compile_gate_covers_canonical_entrypoint_and_packages(self):
        compile_line = (
            "python -m compileall -q actions config core dashboard memory plugins "
            "scripts ui antonella.py main.py ui.py setup.py"
        )
        self.assertGreaterEqual(self.workflow.count(compile_line), 2)

    def test_import_smoke_is_wired_and_utf8_is_pinned(self):
        windows_block = self.workflow.split("windows-baseline:", 1)[1]
        self.assertIn("python scripts/ci_import_smoke.py", windows_block)
        self.assertIn("PYTHONUTF8", windows_block)

    def test_smoke_allows_only_known_missing_runtime_dependencies(self):
        missing_requests = ModuleNotFoundError("No module named 'requests'", name="requests")
        missing_numpy = ModuleNotFoundError("No module named 'numpy'", name="numpy")
        self.assertEqual(
            self.smoke_module._classify_import_error(missing_requests),
            "missing-dep",
        )
        self.assertEqual(
            self.smoke_module._classify_import_error(missing_numpy),
            "missing-dep",
        )

    def test_smoke_unknown_missing_import_fails_closed(self):
        typo = ModuleNotFoundError("No module named 'reqeusts'", name="reqeusts")
        broken_local = ModuleNotFoundError("No module named 'core.missing'", name="core.missing")
        self.assertIsNone(self.smoke_module._classify_import_error(typo))
        self.assertIsNone(self.smoke_module._classify_import_error(broken_local))
        self.assertIn("return 1", self.smoke)

    def test_smoke_never_scans_plugins_dropins(self):
        self.assertNotIn("plugins", self.smoke_module.SMOKE_PACKAGES)


if __name__ == "__main__":
    unittest.main()
