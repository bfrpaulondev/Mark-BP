import unittest

from memory.natural_commands import classify_memory_command


class NaturalCommandTests(unittest.TestCase):
    def test_command_families(self):
        cases = {
            "Aprende que o deploy é às sextas": "learn_fact",
            "Aprende como formatar o disco externo": "learn_procedure",
            "Aprende a formatar o disco externo": "learn_procedure",
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
            "Aprende como faço o relatório",
            "Prefiro ouvir lofi",
            "Corrige o prazo",
            "Esquece Lisboa",
        ):
            with self.subTest(text=text):
                command = classify_memory_command(text)
                self.assertIsNotNone(command)
                self.assertTrue(command.requires_approval)

    def test_read_only_intents_do_not_require_approval(self):
        self.assertFalse(classify_memory_command("Mostra o que sabes sobre deploy").requires_approval)
        self.assertFalse(classify_memory_command("De onde aprendeste o prazo").requires_approval)

    def test_ordinary_sentences_and_prefix_collisions_are_not_memory_commands(self):
        for text in (
            "Que horas são?",
            "Abre o Chrome",
            "Bom dia Antonella",
            "corrigeste o bug ontem",
            "prefirote aqui",
            "esqueceste a chave?",
            "",
            None,
        ):
            with self.subTest(text=text):
                self.assertIsNone(classify_memory_command(text))

    def test_payload_strips_marker_but_preserves_original_casing(self):
        command = classify_memory_command("Aprende que o Projeto EUTAKTOS usa SQL Server")
        self.assertEqual(command.payload, "o Projeto EUTAKTOS usa SQL Server")

    def test_mutation_without_payload_fails_closed(self):
        for text in ("Prefiro", "Corrige", "Esquece", "Aprende que"):
            with self.subTest(text=text):
                self.assertIsNone(classify_memory_command(text))

    def test_read_command_may_have_empty_payload(self):
        command = classify_memory_command("Mostra o que sabes")
        self.assertIsNotNone(command)
        self.assertEqual(command.intent, "list_knowledge")
        self.assertEqual(command.payload, "")

    def test_to_dict_is_safe(self):
        payload = classify_memory_command("Prefiro lofi").to_dict()
        self.assertEqual(set(payload), {"intent", "payload", "requires_approval"})


if __name__ == "__main__":
    unittest.main()
