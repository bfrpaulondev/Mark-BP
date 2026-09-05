import unittest

from core.verifier import claim_safe_message, verify_tool_result


class VerifierTests(unittest.TestCase):
    def test_explicit_verified_json_is_claimable(self):
        result = verify_tool_result(
            '{"action":"mouse_move","ok":true,"delivered":true,"verified":true,"before":[1,2],"after":[3,4]}',
            action="mouse_move",
        )

        self.assertTrue(result.can_claim_success)
        self.assertEqual(result.evidence["before"], [1, 2])
        self.assertEqual(result.evidence["after"], [3, 4])

    def test_ok_without_explicit_verified_remains_unverified(self):
        result = verify_tool_result(
            {"action": "open_app", "ok": True, "delivered": True, "message": "Opened."},
            action="open_app",
        )

        self.assertFalse(result.verified)
        self.assertFalse(result.can_claim_success)

    def test_legacy_done_string_never_becomes_verified(self):
        result = verify_tool_result("Done: next_tab.", action="next_tab")

        self.assertTrue(result.delivered)
        self.assertFalse(result.verified)
        self.assertFalse(result.can_claim_success)
        self.assertIn("not verified", claim_safe_message(result))

    def test_legacy_failure_string_becomes_failure(self):
        result = verify_tool_result(
            "Browser action timed out (60s).",
            action="browser_action",
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.can_claim_success)
        self.assertIn("timed out", result.error)

    def test_error_overrides_inconsistent_verified_payload(self):
        result = verify_tool_result(
            {
                "action": "click",
                "ok": True,
                "delivered": True,
                "verified": True,
                "error": "Target changed before click.",
            },
            action="click",
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.verified)
        self.assertFalse(result.can_claim_success)

    def test_approval_result_cannot_be_claimed_as_complete(self):
        result = verify_tool_result(
            {
                "action": "delete_file",
                "ok": False,
                "delivered": False,
                "verified": False,
                "requires_approval": True,
                "risk": "destructive",
                "message": "Approval required.",
            },
            action="delete_file",
        )

        self.assertTrue(result.requires_approval)
        self.assertEqual(claim_safe_message(result), "Approval required.")


if __name__ == "__main__":
    unittest.main()
