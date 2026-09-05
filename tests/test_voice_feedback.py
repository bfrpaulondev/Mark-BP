from __future__ import annotations

import importlib.util
import itertools
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "antonella_voice_feedback", ROOT / "ui" / "voice_feedback.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

VoiceFeedback = module.VoiceFeedback
cancelled_feedback = module.cancelled_feedback
execution_result_to_voice_feedback = module.execution_result_to_voice_feedback
local_command_feedback = module.local_command_feedback
recovery_feedback = module.recovery_feedback

from core.execution_result import ExecutionResult  # noqa: E402
from core.local_command_router import LocalCommandResult  # noqa: E402


def _result(**overrides) -> ExecutionResult:
    payload = dict(
        action="open_app",
        ok=False,
        delivered=False,
        verified=False,
        error=None,
        requires_approval=False,
    )
    payload.update(overrides)
    return ExecutionResult(**payload)




class LocalCommandFeedbackTests(unittest.TestCase):
    def test_verified_local_command_speaks_success(self):
        feedback = local_command_feedback(
            LocalCommandResult(True, "set_cost", "Modo de custo alterado para economy.", True)
        )
        self.assertEqual(feedback.category, "verified_success")
        self.assertEqual(feedback.phrase_pt, "Modo de custo alterado para economy.")

    def test_unverified_local_command_never_says_success(self):
        feedback = local_command_feedback(
            LocalCommandResult(
                True,
                "open_app",
                "Enviei o pedido para abrir notepad; ainda não verifiquei a janela.",
                False,
            )
        )
        self.assertEqual(feedback.category, "unverified_delivery")
        self.assertIn("não verifiquei", feedback.phrase_pt)

    def test_error_message_is_passed_through_without_success_claim(self):
        # LocalCommandResult has no error field: handled+unverified maps to
        # unverified_delivery, and the honest human message stays untouched.
        feedback = local_command_feedback(
            LocalCommandResult(True, "scroll", "Não consegui executar o scroll.", False)
        )
        self.assertEqual(feedback.category, "unverified_delivery")
        self.assertIn("Não consegui executar", feedback.phrase_pt)
        self.assertNotIn("Concluído", feedback.phrase_pt)

    def test_unhandled_result_is_failure(self):
        feedback = local_command_feedback(LocalCommandResult(False, "open_app", "", False))
        self.assertEqual(feedback.category, "failure")
        self.assertEqual(feedback.phrase_pt, "Não consegui concluir.")

    def test_unverified_empty_message_gets_honest_fallback(self):
        feedback = local_command_feedback(LocalCommandResult(True, "scroll", "", False))
        self.assertEqual(feedback.category, "unverified_delivery")
        self.assertIn("não consegui confirmar", feedback.phrase_pt)

    def test_verifier_result_wins_over_router_result(self):
        feedback = local_command_feedback(
            LocalCommandResult(True, "open_app", "Enviei o pedido.", False),
            verification=ExecutionResult.verified_success("open_app"),
        )
        self.assertEqual(feedback.category, "verified_success")

    def test_failed_verifier_result_wins(self):
        feedback = local_command_feedback(
            LocalCommandResult(True, "open_app", "Enviei o pedido.", False),
            verification=ExecutionResult.failure("open_app", "janela não apareceu"),
        )
        self.assertEqual(feedback.category, "failure")

    def test_non_local_command_result_fails_closed(self):
        feedback = local_command_feedback({"ok": True, "verified": True, "message": "x"})
        self.assertEqual(feedback.category, "failure")


class VoiceFeedbackMappingTests(unittest.TestCase):
    def test_verified_success_is_the_only_success_category(self):
        feedback = execution_result_to_voice_feedback(
            _result(ok=True, delivered=True, verified=True)
        )
        self.assertEqual(feedback.category, "verified_success")
        self.assertEqual(feedback.phrase_pt, "Concluído.")

    def test_delivered_but_unverified_never_says_success(self):
        feedback = execution_result_to_voice_feedback(
            _result(ok=True, delivered=True, verified=False)
        )
        self.assertEqual(feedback.category, "unverified_delivery")
        self.assertIn("não consegui confirmar", feedback.phrase_pt)

    def test_failure_is_human_and_short(self):
        feedback = execution_result_to_voice_feedback(
            _result(ok=False, error="PlaywrightTimeoutError 0x80070002")
        )
        self.assertEqual(feedback.category, "failure")
        self.assertEqual(feedback.phrase_pt, "Não consegui concluir.")
        self.assertNotIn("Playwright", feedback.phrase_pt)

    def test_waiting_approval_never_announces_success(self):
        feedback = execution_result_to_voice_feedback(
            _result(ok=True, delivered=True, verified=True, requires_approval=True)
        )
        self.assertEqual(feedback.category, "waiting_approval")
        self.assertIn("aprovação", feedback.phrase_pt)

    def test_cancelled_is_its_own_category(self):
        feedback = cancelled_feedback()
        self.assertEqual(feedback.category, "cancelled")
        self.assertEqual(feedback.phrase_pt, "Cancelado.")
        self.assertNotEqual(feedback.category, "failure")

    def test_recovery_is_short_and_calm(self):
        feedback = recovery_feedback()
        self.assertEqual(feedback.category, "recovery")
        self.assertIn("tentar novamente", feedback.phrase_pt)

    def test_untrusted_mapping_cannot_forge_verified_success(self):
        forged = {
            "action": "delete_file",
            "ok": True,
            "delivered": True,
            "verified": True,
            "requires_approval": False,
        }
        feedback = execution_result_to_voice_feedback(forged)
        self.assertEqual(feedback.category, "failure")
        self.assertNotEqual(feedback.phrase_pt, "Concluído.")

    def test_unknown_and_malformed_inputs_fail_closed(self):
        for bad in ({}, {"ok": "yes"}, None, "garbage", 42):
            with self.subTest(bad=bad):
                feedback = execution_result_to_voice_feedback(bad)
                self.assertEqual(feedback.category, "failure")

    def test_property_no_success_speech_before_verified_success(self):
        for ok, delivered, verified, has_error, requires_approval in itertools.product(
            (False, True), repeat=5
        ):
            with self.subTest(
                ok=ok,
                delivered=delivered,
                verified=verified,
                has_error=has_error,
                requires_approval=requires_approval,
            ):
                feedback = execution_result_to_voice_feedback(
                    _result(
                        ok=ok,
                        delivered=delivered,
                        verified=verified,
                        error="x" if has_error else None,
                        requires_approval=requires_approval,
                    )
                )
                if feedback.category == "verified_success":
                    self.assertTrue(
                        ok
                        and delivered
                        and verified
                        and not has_error
                        and not requires_approval
                    )

    def test_phrases_never_carry_evidence_content(self):
        feedback = execution_result_to_voice_feedback(
            ExecutionResult(
                action="open_app",
                ok=True,
                delivered=True,
                verified=True,
                evidence={"secret": "SUPER-SECRET-VALUE"},
            )
        )
        self.assertNotIn("SUPER-SECRET-VALUE", feedback.phrase_pt)

    def test_feedback_is_frozen_and_categories_are_valid(self):
        feedback = cancelled_feedback()
        with self.assertRaises(Exception):
            feedback.category = "failure"  # type: ignore[misc]
        self.assertIn(feedback.category, module.CATEGORIES)


if __name__ == "__main__":
    unittest.main()
