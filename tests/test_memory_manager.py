import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import memory_manager


class MemoryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.temp_dir.name) / "memory" / "long_term.json"
        self.path_patch = patch.object(memory_manager, "MEMORY_PATH", self.memory_path)
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_update_memory_persists_and_formats_identity(self):
        memory_manager.update_memory(
            {"identity": {"name": {"value": "Bruno"}}}
        )

        loaded = memory_manager.load_memory()
        prompt = memory_manager.format_memory_for_prompt(loaded)

        self.assertEqual(loaded["identity"]["name"]["value"], "Bruno")
        self.assertIn("Name: Bruno", prompt)

    def test_blank_update_does_not_create_an_entry(self):
        memory_manager.update_memory(
            {"preferences": {"editor": {"value": "   "}}}
        )

        loaded = memory_manager.load_memory()

        self.assertNotIn("editor", loaded["preferences"])

    def test_forget_removes_only_the_requested_entry(self):
        memory_manager.remember("editor", "VS Code", "preferences")
        memory_manager.remember("language", "Portuguese", "identity")

        result = memory_manager.forget("editor", "preferences")
        loaded = memory_manager.load_memory()

        self.assertEqual(result, "Forgotten: preferences/editor")
        self.assertNotIn("editor", loaded["preferences"])
        self.assertEqual(loaded["identity"]["language"]["value"], "Portuguese")

    def test_session_summary_is_consumed_once(self):
        memory_manager.save_session_summary("Worked on the Antonella baseline.", "Portuguese")

        first = memory_manager.pop_last_session()
        second = memory_manager.pop_last_session()

        self.assertEqual(first["summary"], "Worked on the Antonella baseline.")
        self.assertEqual(first["language"], "Portuguese")
        self.assertIsNone(second)


if __name__ == "__main__":
    unittest.main()
