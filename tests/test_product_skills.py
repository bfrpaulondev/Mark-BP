"""BLOCO 13 — the four product skill packages must be valid drafts."""
import unittest
from pathlib import Path

from core.skills.manifest import SkillManifest, validate_manifest

ROOT = Path(__file__).resolve().parent.parent
SKILL_SLUGS = ("daily-report", "meeting-copilot", "meeting-action-items", "workday-summary")


class ProductSkillDraftsTests(unittest.TestCase):
    def test_all_four_packages_exist_with_required_files(self):
        for slug in SKILL_SLUGS:
            with self.subTest(slug=slug):
                pkg = ROOT / "skills" / slug
                self.assertTrue((pkg / "SKILL.md").is_file())
                self.assertTrue((pkg / "manifest.yaml").is_file())
                self.assertTrue((pkg / "skill.py").is_file())
                self.assertTrue(any((pkg / "tests").glob("test_*.py")))

    def test_manifests_are_valid_and_draft_safe(self):
        for slug in SKILL_SLUGS:
            with self.subTest(slug=slug):
                text = (ROOT / "skills" / slug / "manifest.yaml").read_text(encoding="utf-8")
                manifest = SkillManifest.from_dict(_load_yaml(text))
                self.assertEqual(validate_manifest(manifest), [])
                self.assertEqual(manifest.permissions, ())
                self.assertEqual(manifest.risk, "low")


def _load_yaml(text: str) -> dict:
    """Minimal loader mirroring the restricted manifest subset."""
    data = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            value = value.strip()
            data[key.strip()] = [] if value == "[]" else value
    return data


if __name__ == "__main__":
    unittest.main()
