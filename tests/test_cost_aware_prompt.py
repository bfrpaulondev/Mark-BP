import unittest
from pathlib import Path


class CostAwarePromptTests(unittest.TestCase):
    def test_prompt_keeps_realtime_computer_use_as_last_resort(self):
        prompt = (
            Path(__file__).resolve().parent.parent / "core" / "prompt.txt"
        ).read_text(encoding="utf-8")
        normalized = prompt.lower()

        self.assertIn("cost-aware tool routing", normalized)
        self.assertIn("direct/local tools first", normalized)
        self.assertIn("structured application tools next", normalized)
        self.assertIn("realtime_computer_use only", normalized)
        self.assertIn("default computer use to economy", normalized)
        self.assertIn("token/cost efficiency", normalized)


if __name__ == "__main__":
    unittest.main()
