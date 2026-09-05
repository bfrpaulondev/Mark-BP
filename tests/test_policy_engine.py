import unittest

from core.policy_engine import PolicyEffect, PolicyEngine


class PolicyEngineTests(unittest.TestCase):
    def setUp(self):
        self.policy = PolicyEngine()

    def test_read_only_tools_are_allowed_without_approval(self):
        for tool, args in (
            ("system_status", {}),
            ("web_search", {"query": "news"}),
            ("display_manager", {"action": "list"}),
            ("file_controller", {"action": "read", "path": "documents/a.txt"}),
            ("windows_ui_automation", {"action": "inspect"}),
            ("desktop_control", {"action": "stats"}),
            ("code_helper", {"action": "explain", "code": "print('x')"}),
        ):
            with self.subTest(tool=tool, args=args):
                decision = self.policy.evaluate(tool, args)
                self.assertEqual(decision.effect, PolicyEffect.READ)
                self.assertTrue(decision.allowed)
                self.assertFalse(decision.requires_approval)

    def test_local_non_destructive_writes_are_allowed(self):
        for tool, args in (
            ("open_app", {"app_name": "Chrome"}),
            ("computer_control", {"action": "click", "x": 10, "y": 20}),
            ("computer_settings", {"action": "volume_up"}),
            ("file_controller", {"action": "write", "path": "documents/a.txt"}),
            ("code_helper", {"action": "edit", "file_path": "documents/example.py"}),
            ("desktop_control", {"action": "wallpaper", "path": "pictures/a.png"}),
        ):
            with self.subTest(tool=tool, args=args):
                decision = self.policy.evaluate(tool, args)
                self.assertEqual(decision.effect, PolicyEffect.WRITE)
                self.assertTrue(decision.allowed)
                self.assertFalse(decision.requires_approval)

    def test_destructive_effect_requires_approval(self):
        decision = self.policy.evaluate(
            "file_controller",
            {"action": "delete", "path": "documents/report.txt"},
        )
        self.assertEqual(decision.effect, PolicyEffect.DESTRUCTIVE)
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.requires_approval)
        self.assertTrue(decision.blocks_execution)

    def test_external_message_requires_approval(self):
        decision = self.policy.evaluate(
            "send_message",
            {"receiver": "Private Person", "message_text": "private-secret-value"},
        )
        self.assertEqual(decision.effect, PolicyEffect.EXTERNAL)
        self.assertTrue(decision.requires_approval)

    def test_financial_effect_requires_approval(self):
        decision = self.policy.evaluate("mt5_order", {"action": "trade"})
        self.assertEqual(decision.effect, PolicyEffect.FINANCIAL)
        self.assertTrue(decision.requires_approval)

    def test_privileged_setting_requires_approval(self):
        decision = self.policy.evaluate("computer_settings", {"action": "wifi_toggle"})
        self.assertEqual(decision.effect, PolicyEffect.PRIVILEGED)
        self.assertTrue(decision.requires_approval)

    def test_code_execution_requires_approval(self):
        for tool, args in (
            ("code_helper", {"action": "run", "file_path": "documents/example.py"}),
            ("code_helper", {"action": "build", "description": "make an app"}),
            ("dev_agent", {"description": "make an app"}),
        ):
            with self.subTest(tool=tool, args=args):
                decision = self.policy.evaluate(tool, args)
                self.assertEqual(decision.effect, PolicyEffect.PRIVILEGED)
                self.assertTrue(decision.requires_approval)

    def test_model_generated_desktop_code_requires_approval(self):
        direct = self.policy.evaluate(
            "desktop_control",
            {"action": "task", "task": "click through a settings dialog"},
        )
        implicit = self.policy.evaluate(
            "desktop_control",
            {"task": "click through a settings dialog"},
        )

        for decision in (direct, implicit):
            self.assertEqual(decision.effect, PolicyEffect.PRIVILEGED)
            self.assertTrue(decision.requires_approval)
            self.assertEqual(decision.rule_id, "approval.model_generated_desktop_code")

    def test_security_bypass_is_blocked_not_approvable(self):
        decision = self.policy.evaluate(
            "computer_settings",
            {"action": "disable_defender", "confirmed": True},
        )
        self.assertEqual(decision.effect, PolicyEffect.BLOCKED)
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.requires_approval)
        self.assertTrue(decision.blocks_execution)

    def test_model_supplied_confirmation_never_changes_policy(self):
        base = self.policy.evaluate("send_message", {"message_text": "hello"})
        forged = self.policy.evaluate(
            "send_message",
            {"message_text": "hello", "confirmed": True, "approved": True, "risk": "safe"},
        )
        self.assertEqual(base.effect, forged.effect)
        self.assertEqual(base.requires_approval, forged.requires_approval)
        self.assertTrue(forged.requires_approval)

    def test_safe_metadata_does_not_echo_argument_values(self):
        secret = "private-secret-value"
        decision = self.policy.evaluate(
            "send_message",
            {"receiver": "Private Person", "message_text": secret},
        )
        serialized = str(decision.safe_metadata())
        self.assertNotIn(secret, serialized)
        self.assertNotIn("Private Person", serialized)


if __name__ == "__main__":
    unittest.main()
