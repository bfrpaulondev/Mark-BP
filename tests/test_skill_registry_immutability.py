import unittest

from core.skills.registry import SkillRegistry


class SkillRegistryImmutabilityTests(unittest.TestCase):
    def test_identical_reregistration_is_idempotent_and_preserves_state(self):
        registry = SkillRegistry()
        first = registry.register("daily-report", "1.0.0", ("filesystem.read",), "low")
        registry.transition("daily-report", "validating", "1.0.0")

        again = registry.register("daily-report", "1.0.0", ("filesystem.read",), "low")

        self.assertIs(first, again)
        self.assertEqual(again.state, "validating")

    def test_same_version_cannot_change_permissions(self):
        registry = SkillRegistry()
        registry.register("daily-report", "1.0.0", ("filesystem.read",), "low")

        with self.assertRaises(ValueError):
            registry.register(
                "daily-report",
                "1.0.0",
                ("filesystem.read", "filesystem.write"),
                "low",
            )

    def test_same_version_cannot_change_risk_after_activation(self):
        registry = SkillRegistry()
        registry.register("daily-report", "1.0.0", (), "low")
        registry.transition("daily-report", "validating", "1.0.0")
        registry.transition("daily-report", "tested", "1.0.0")
        registry.transition("daily-report", "awaiting_approval", "1.0.0")
        registry.transition("daily-report", "active", "1.0.0")

        with self.assertRaises(ValueError):
            registry.register("daily-report", "1.0.0", (), "medium")

        self.assertEqual(registry.active_version("daily-report"), "1.0.0")
        self.assertEqual(registry.get_version("daily-report", "1.0.0").risk, "low")


if __name__ == "__main__":
    unittest.main()
