import unittest

from memory.natural_commands import classify_memory_command


class NaturalCommandTests(unittest.TestCase):
    def test_six_command_families(self):
        cases = {
            "Aprende que o deploy é às sextas": "learn_fact",
            "Aprende a formatar o disco externo": "learn_fact",
            "Prefiro ouvir lofi quando programo": "preference",
            "Corrige o deadline do projeto": "correct",
            "Esquece que estive em Lisboa": "forget",
            "Mostra o que sabes sobre deploy": "list_knowledge",
            "De onde aprendeste o valor do deploy": "explain_source",
        }
        for text, intent in cases.items():
            with self.subTest(text=text):
                command = classify_memory_command(text)
                self.assertIsNotNone(command)
                self.assertEqual(command.intent, intent)

    def test_mutating_intents_always_require_approval(self):
        for text in (
            "Aprende que o deploy é às sextas",
            "Prefiro ouvir lofi",
            "Corrige o prazo",
            "Esquece Lisboa",
        ):
            with self.subTest(text=text):
                self.assertTrue(classify_memory_command(text).requires_approval)

    def test_read_only_intents_do_not_require_approval(self):
        self.assertFalse(classify_memory_command("Mostra o que sabes sobre deploy").requires_approval)
        self.assertFalse(classify_memory_command("De onde aprendeste o prazo").requires_approval)

    def test_ordinary_sentences_are_not_memory_commands(self):
        for text in ("Que horas são?", "Abre o Chrome", "Bom dia Antonella", "", None):
            with self.subTest(text=text):
                self.assertIsNone(classify_memory_command(text))

    def test_payload_strips_the_marker(self):
        command = classify_memory_command("Aprende que o deploy é às sextas")
        self.assertEqual(command.payload, "o deploy é às sextas")

    def test_to_dict_is_safe(self):
        payload = classify_memory_command("Prefiro lofi").to_dict()
        self.assertEqual(set(payload), {"intent", "payload", "requires_approval"})


if __name__ == "__main__":
    unittest.main()
