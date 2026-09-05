import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.file_controller import file_controller
from core.file_postconditions import capture_file_state, verify_file_postcondition
from core.postcondition_verifiers import verify_postcondition


class FilePostconditionTests(unittest.TestCase):
    def test_create_file_is_verified_without_exposing_content(self):
        secret = "private-content-123"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = {"action": "create_file", "path": str(root), "name": "note.txt", "content": secret}
            before = capture_file_state(args)
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                raw = file_controller(args)
            execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertNotIn(secret, json.dumps(execution.to_dict(), ensure_ascii=False))
        self.assertEqual(execution.evidence["after_source"]["size"], len(secret.encode("utf-8")))

    def test_write_reloads_file_and_verifies_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "data.txt"
            target.write_text("before", encoding="utf-8")
            args = {"action": "write", "path": str(target), "content": "after"}
            before = capture_file_state(args)
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                raw = file_controller(args)
            execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertEqual(execution.evidence["after_source"]["size"], 5)

    def test_move_to_preexisting_directory_uses_pre_action_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.txt"
            source.write_text("payload", encoding="utf-8")
            destination = root / "archive"
            destination.mkdir()
            args = {
                "action": "move",
                "path": str(source),
                "destination": str(destination),
            }
            before = capture_file_state(args)
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                raw = file_controller(args)
            execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertFalse(execution.evidence["after_source"]["exists"])
        self.assertTrue(execution.evidence["after_destination"]["exists"])

    def test_move_to_new_destination_does_not_reinterpret_path_after_move(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "folder"
            source.mkdir()
            (source / "item.txt").write_text("payload", encoding="utf-8")
            destination = root / "moved-folder"
            args = {
                "action": "move",
                "path": str(source),
                "destination": str(destination),
            }
            before = capture_file_state(args)
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                raw = file_controller(args)
            execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertTrue(execution.evidence["after_destination"]["exists"])

    def test_delete_requires_source_to_disappear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "delete-me.txt"
            target.write_text("payload", encoding="utf-8")
            args = {"action": "delete", "path": str(target)}
            before = capture_file_state(args)
            target.unlink()
            execution = verify_file_postcondition(args, before_state=before, delivered=True)

        self.assertTrue(execution.can_claim_success)

    def test_unchanged_delete_remains_unverified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "keep-me.txt"
            target.write_text("payload", encoding="utf-8")
            args = {"action": "delete", "path": str(target)}
            before = capture_file_state(args)
            execution = verify_file_postcondition(args, before_state=before, delivered=True)

        self.assertFalse(execution.verified)
        self.assertTrue(execution.delivered)


if __name__ == "__main__":
    unittest.main()
