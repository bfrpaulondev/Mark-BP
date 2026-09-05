import os
import unittest
from unittest.mock import patch

from core.local_command_router import (
    LocalCommandIntent,
    execute_local_intent,
    parse_local_text_command,
)


class LocalCommandRouterTests(unittest.TestCase):
    def test_simple_app_launch_is_local(self):
        intent = parse_local_text_command("abre Chrome")

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind, "open_app")
        self.assertEqual(intent.args["app_name"], "Chrome")

    def test_multistep_app_request_is_not_intercepted(self):
        self.assertIsNone(
            parse_local_text_command("abre Chrome e pesquisa restaurantes em Setúbal")
        )
        self.assertIsNone(
            parse_local_text_command("open Chrome and then search for documentation")
        )

    def test_portuguese_display_and_agent_commands_are_local(self):
        self.assertEqual(parse_local_text_command("que ecrãs tenho?").kind, "display_list")
        self.assertEqual(parse_local_text_command("status do agente").kind, "agent_status")
        self.assertEqual(parse_local_text_command("parar Computer Use").kind, "agent_stop")
        self.assertEqual(parse_local_text_command("aprovar passo").kind, "agent_approve")

    def test_scroll_is_conservative_and_bounded(self):
        intent = parse_local_text_command("scroll para baixo 99")

        self.assertEqual(intent.kind, "scroll")
        self.assertEqual(intent.args["direction"], "down")
        self.assertEqual(intent.args["amount"], 12)

    def test_cost_aliases_do_not_require_model(self):
        self.assertEqual(
            parse_local_text_command("modo económico").args["mode"],
            "economy",
        )
        self.assertEqual(
            parse_local_text_command("modo equilibrado").args["mode"],
            "balanced",
        )
        self.assertEqual(
            parse_local_text_command("modo qualidade").args["mode"],
            "quality",
        )

    def test_cost_and_provider_execution_only_change_the_target_env_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            cost = execute_local_intent(
                LocalCommandIntent("set_cost", {"mode": "economy"})
            )
            provider = execute_local_intent(
                LocalCommandIntent("set_provider", {"provider": "openai"})
            )

            self.assertTrue(cost.handled)
            self.assertTrue(provider.handled)
            self.assertEqual(os.environ["ANTONELLA_COMPUTER_USE_COST_MODE"], "economy")
            self.assertEqual(os.environ["ANTONELLA_MODEL_PROVIDER_PREFERENCE"], "openai")
            self.assertNotIn("ANTONELLA_OPENAI_API_KEY", os.environ)
            self.assertNotIn("ANTONELLA_GEMINI_API_KEY", os.environ)

    def test_unknown_or_complex_request_falls_back_to_primary_brain(self):
        for text in (
            "explica-me a arquitectura do projecto",
            "descobre onde estão as permissões neste ScreenConnect",
            "abre Chrome e depois preenche o formulário",
        ):
            self.assertIsNone(parse_local_text_command(text), text)


if __name__ == "__main__":
    unittest.main()
