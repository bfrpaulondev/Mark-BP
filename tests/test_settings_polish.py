import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class SettingsPolishContractTests(unittest.TestCase):
    """Settings dialog: explicit commit, visible focus and accessibility."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "ui" / "settings_dialog.py").read_text(encoding="utf-8")

    def test_commit_is_excluded_from_keyboard_default(self):
        self.assertEqual(self.source.count("setAutoDefault(False)"), 2)
        self.assertEqual(self.source.count("setDefault(False)"), 2)
        self.assertIn("class ExplicitCommitButton", self.source)
        self.assertIn("Qt.Key.Key_Return", self.source)
        self.assertIn("Qt.Key.Key_Enter", self.source)

    def test_buttons_have_visible_focus_and_accessible_names(self):
        self.assertIn("QPushButton:focus", self.source)
        self.assertIn('setAccessibleName("Aplicar preferências")', self.source)
        self.assertIn('setAccessibleName("Cancelar alterações")', self.source)

    def test_module_constants_are_self_consistent(self):
        defined = set(re.findall(r"^_([A-Z][A-Z0-9_]*) =", self.source, flags=re.M))
        used = set(re.findall(r"\b_([A-Z][A-Z0-9_]*)\b", self.source))
        missing = {f"_{name}" for name in used if name not in defined}
        self.assertEqual(missing, set(), f"undefined module constants: {missing}")


if __name__ == "__main__":
    unittest.main()
