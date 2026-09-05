import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_EXACT = ("JARVIS", "Tony Stark", "MARK LI")


class LegacyInaccessibilityTests(unittest.TestCase):
    """B3 — prove the legacy UI module cannot reach the modern runtime."""

    @classmethod
    def setUpClass(cls):
        cls.entrypoints = {
            name: (ROOT / name).read_text(encoding="utf-8")
            for name in ("antonella.py", "main.py")
        }

    def test_package_shadows_legacy_module_in_runtime(self):
        # Runtime proof: importing `ui` resolves to the package, never the
        # legacy file. Needs PyQt6 → skipped on dependency-free CI legs.
        try:
            import ui  # noqa: F401
        except ImportError:
            self.skipTest("PyQt6 unavailable: dependency-free CI leg")
        self.assertTrue(str(ui.__file__).replace("\\", "/").endswith("ui/__init__.py"))

    def test_legacy_file_is_removed(self):
        # B4: the legacy module is gone — there is nothing left to execute
        # or import accidentally.
        self.assertFalse((ROOT / "ui.py").exists())

    def test_entrypoints_import_the_ui_package(self):
        for name, source in self.entrypoints.items():
            with self.subTest(entrypoint=name):
                self.assertIn("from ui import", source)
                self.assertNotIn("from ui.py import", source)
                self.assertNotIn("import ui.py", source)


class IdentityRegressionTests(unittest.TestCase):
    """B5 — live runtime surfaces must never show legacy product tokens.

    Only exact product tokens are forbidden; bare personal names
    (e.g. "Mark") are intentionally NOT scanned.
    """

    @classmethod
    def setUpClass(cls):
        cls.live_sources = {
            name: (ROOT / name).read_text(encoding="utf-8")
            for name in ("main.py", "antonella.py")
        }
        cls.ui_sources = {
            str(path): path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "ui").glob("*.py"))
        }

    def test_entrypoints_carry_no_legacy_tokens(self):
        for name, source in self.live_sources.items():
            with self.subTest(entrypoint=name):
                for token in FORBIDDEN_EXACT:
                    if name == "antonella.py" and token == "JARVIS":
                        continue  # prohibition in the identity prompt, tested below
                    self.assertNotIn(token, source)

    def test_legacy_tokens_appear_only_as_prohibitions(self):
        # The identity prompt must keep PROHIBITING the old names; that is
        # the only legitimate occurrence of a legacy token in live code.
        source = self.live_sources["antonella.py"]
        occurrences = [line for line in source.splitlines() if "JARVIS" in line]
        self.assertTrue(occurrences, "identity prohibition must stay present")
        for line in occurrences:
            self.assertIn("Do not call yourself", line)

    def test_ui_surfaces_carry_no_legacy_tokens(self):
        for path, source in self.ui_sources.items():
            with self.subTest(surface=path):
                for line in source.splitlines():
                    for token in FORBIDDEN_EXACT:
                        if token in line:
                            # The LogView masking mechanism legitimately
                            # contains the tokens it removes from view.
                            is_masking = '.replace("' in line and "assistant_name" in line
                            self.assertTrue(
                                is_masking,
                                f"{path}: legacy token outside masking: {line.strip()[:80]}",
                            )

    def test_fallback_system_prompt_is_identity_neutral(self):
        self.assertIn("You are the user's desktop assistant.", self.live_sources["main.py"])

    def test_prompt_file_keeps_prohibiting_legacy_names(self):
        # core/prompt.txt must keep telling the model NOT to use old names
        # (the only allowed occurrences of legacy tokens are prohibitions
        # and internal legacy tool names that must never be spoken).
        prompt = (ROOT / "core" / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("Never call yourself JARVIS", prompt)


if __name__ == "__main__":
    unittest.main()
