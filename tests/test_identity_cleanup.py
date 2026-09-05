import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class IdentityCleanupTests(unittest.TestCase):
    """ANT-272 — visible surfaces must read Antonella; legacy internals stay."""

    @classmethod
    def setUpClass(cls):
        cls.live_ui = (ROOT / "ui" / "__init__.py").read_text(encoding="utf-8")
        cls.legacy_ui = (ROOT / "ui.py").read_text(encoding="utf-8")

    def test_dead_legacy_ui_has_no_mark_li_titles(self):
        self.assertNotIn("MARK LI", self.legacy_ui)

    def test_logview_masks_exact_legacy_product_token(self):
        self.assertIn('.replace("MARK LI", self.assistant_name)', self.live_ui)

    def test_logview_never_masks_bare_mark_personal_name(self):
        # "Mark" is a common personal name; masking it would corrupt real
        # user content. Only the exact product token is rewritten.
        self.assertNotIn('.replace("Mark ",', self.live_ui)
        self.assertNotIn('.replace("MARK ",', self.live_ui)

    def test_live_window_titles_are_antonella(self):
        self.assertIn('self.setWindowTitle("Antonella")', self.live_ui)

    def test_internal_class_names_are_out_of_scope(self):
        # No mass rename: JarvisUI remains the internal compatibility name.
        self.assertIn("class JarvisUI", self.live_ui)


if __name__ == "__main__":
    unittest.main()
