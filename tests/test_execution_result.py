import unittest

from core.execution_result import ExecutionResult, normalize_execution_result


class ExecutionResultTests(unittest.TestCase):
    def test_verified_success_can_be_claimed(self):
        result = ExecutionResult.verified_success(
            "mouse_move",
            evidence={"before": [1, 2], "after": [10, 20]},
        )

        self.assertTrue(result.can_claim_success)
        self.assertTrue(result.to_dict()["verified"])

    def test_unverified_delivery_cannot_be_claimed_as_success(self):
        result = ExecutionResult.unverified_delivery(
            "scroll",
            message="Shortcut delivered but effect was not observed.",
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.delivered)
        self.assertFalse(result.verified)
        self.assertFalse(result.can_claim_success)

    def test_failure_never_claims_success(self):
        result = ExecutionResult.failure(
            "browser_next_tab",
            "No visible browser window.",
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.can_claim_success)
        self.assertEqual(result.error, "No visible browser window.")

    def test_normalizer_never_infers_verification_from_ok(self):
        result = normalize_execution_result(
            {"ok": True, "delivered": True, "message": "Done."},
            action="legacy_action",
        )

        self.assertFalse(result.verified)
        self.assertFalse(result.can_claim_success)

    def test_approval_requirement_survives_normalization(self):
        result = normalize_execution_result(
            {
                "action": "delete_file",
                "ok": False,
                "delivered": False,
                "verified": False,
                "risk": "destructive",
                "requires_approval": True,
                "error": "Approval required.",
            }
        )

        self.assertTrue(result.requires_approval)
        self.assertEqual(result.risk, "destructive")


if __name__ == "__main__":
    unittest.main()
