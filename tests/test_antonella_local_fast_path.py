import unittest
from pathlib import Path


class AntonellaLocalFastPathTests(unittest.TestCase):
    def test_typed_fast_path_runs_before_live_session_fallback(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "antonella.py").read_text(encoding="utf-8")

        parse_call = "intent = parse_local_text_command(text)"
        live_fallback = 'self._schedule_realtime_text(text, label="text input")'

        self.assertIn(parse_call, source)
        self.assertIn("execute_local_intent", source)
        self.assertIn(live_fallback, source)
        self.assertLess(source.index(parse_call), source.index(live_fallback))
        self.assertIn("fast path local", source)
        self.assertIn("antonella-local-", source)

    def test_fast_path_open_app_rechecks_real_app_state(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "antonella.py").read_text(encoding="utf-8")

        self.assertIn("verify_open_app_postcondition", source)
        self.assertIn("capture_open_app_state", source)
        self.assertLess(
            source.index("capture_open_app_state(app_name)"),
            source.index("execute_local_intent(intent, player=self.ui)"),
        )
        self.assertIn('intent.kind == "open_app"', source)
        self.assertIn("verification.can_claim_success", source)
        self.assertIn("fast-path open_app", source)

    def test_local_router_has_no_provider_sdk_dependency(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "core" / "local_command_router.py").read_text(encoding="utf-8")

        self.assertNotIn("google.genai", source)
        self.assertNotIn("import openai", source)
        self.assertNotIn("from openai", source)
        self.assertIn("parse_local_text_command", source)
        self.assertIn("execute_local_intent", source)


if __name__ == "__main__":
    unittest.main()
