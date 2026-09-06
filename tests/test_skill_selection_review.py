import unittest

from core.skills.registry import SkillRegistry
from core.skills.selection import MAX_SELECTED_SKILLS, select_skills


def _activate(registry: SkillRegistry, slug: str, version: str = "1.0.0", permissions=()):
    registry.register(slug, version, tuple(permissions), "low")
    for state in ("validating", "tested", "awaiting_approval", "active"):
        registry.transition(slug, state, version)


class SkillSelectionReviewTests(unittest.TestCase):
    def test_zero_overlap_skill_is_not_selected(self):
        registry = SkillRegistry()
        _activate(registry, "daily-report")

        selection = select_skills(registry, intent_text="abrir o navegador")

        self.assertEqual(selection.ranked, [])
        self.assertEqual(selection.excluded[0]["reason"], "no deterministic relevance match")

    def test_metadata_allows_portuguese_daily_report_match(self):
        registry = SkillRegistry()
        _activate(registry, "daily-report")

        selection = select_skills(
            registry,
            intent_text="prepara o relatório diário",
            metadata_by_slug={
                "daily-report": {
                    "name": "Relatório diário",
                    "triggers": ["relatório diário", "daily report"],
                }
            },
        )

        self.assertEqual([item["slug"] for item in selection.ranked], ["daily-report"])
        self.assertGreater(selection.ranked[0]["score"], 0)

    def test_accents_are_normalized(self):
        registry = SkillRegistry()
        _activate(registry, "meeting-action-items")

        selection = select_skills(
            registry,
            intent_text="ações da reunião",
            metadata_by_slug={"meeting-action-items": "acoes reunião"},
        )

        self.assertEqual(selection.ranked[0]["slug"], "meeting-action-items")

    def test_top_k_is_hard_bounded(self):
        registry = SkillRegistry()
        metadata = {}
        for index in range(MAX_SELECTED_SKILLS + 5):
            slug = f"report-{index}"
            _activate(registry, slug)
            metadata[slug] = "report"

        selection = select_skills(
            registry,
            intent_text="report",
            top_k=10_000,
            metadata_by_slug=metadata,
        )

        self.assertEqual(len(selection.ranked), MAX_SELECTED_SKILLS)

    def test_permissions_still_fail_closed(self):
        registry = SkillRegistry()
        _activate(registry, "daily-report", permissions=("filesystem.read",))

        selection = select_skills(
            registry,
            intent_text="daily report",
            granted_permissions=set(),
        )

        self.assertEqual(selection.ranked, [])
        self.assertIn("filesystem.read", selection.excluded[0]["reason"])


if __name__ == "__main__":
    unittest.main()
