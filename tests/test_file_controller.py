import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions import file_controller


class FileControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.safe_root = Path(self.temp_dir.name).resolve()
        self.safe_roots_patch = patch.object(file_controller, "_SAFE_ROOTS", [self.safe_root])
        self.safe_roots_patch.start()

    def tearDown(self):
        self.safe_roots_patch.stop()
        self.temp_dir.cleanup()

    def test_dispatch_creates_writes_and_reads_a_file(self):
        created = file_controller.file_controller(
            {"action": "create_file", "path": str(self.safe_root), "name": "note.txt", "content": "first"}
        )
        written = file_controller.file_controller(
            {"action": "write", "path": str(self.safe_root), "name": "note.txt", "content": "second"}
        )
        content = file_controller.file_controller(
            {"action": "read", "path": str(self.safe_root), "name": "note.txt"}
        )

        self.assertEqual(created, "File created: note.txt")
        self.assertEqual(written, "Written to: note.txt")
        self.assertEqual(content, "second")

    def test_dispatch_rejects_a_path_outside_the_allowed_root(self):
        outside = self.safe_root.parent / "outside-antonella-test.txt"

        result = file_controller.file_controller(
            {"action": "create_file", "path": str(outside), "content": "blocked"}
        )

        self.assertIn("Access denied", result)
        self.assertFalse(outside.exists())

    def test_dispatch_reports_unknown_action(self):
        result = file_controller.file_controller({"action": "not-supported"})

        self.assertEqual(result, "Unknown action: 'not-supported'")


if __name__ == "__main__":
    unittest.main()
