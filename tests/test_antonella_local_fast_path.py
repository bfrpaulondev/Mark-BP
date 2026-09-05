import unittest
from pathlib import Path


class AntonellaLocalFastPathTests(unittest.TestCase):
    def test_typed_fast_path_runs_before_live_session_fallback(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "antonella.py").read_text(encoding="utf-8")

        self.assertIn("parse_local_text_command(text)", source)
        self.assertIn("execute_local_intent", source)
        self.assertIn("super()._on_text_command(text)", source)
        self.assertIn("fast path local", source)
        self.assertIn("antonella-local-", source)

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
