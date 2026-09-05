import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.file_controller import file_controller
from core.file_postconditions import (
    _file_digest,
    _payload_digest,
    capture_file_state,
    verify_file_postcondition,
)
from core.postcondition_verifiers import verify_postcondition


class FilePostconditionTests(unittest.TestCase):
    def test_create_file_is_verified_without_exposing_content(self):
        secret = "private-content-123"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = {"action": "create_file", "path": str(root), "name": "note.txt", "content": secret}
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                raw = file_controller(args)
                execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertNotIn(secret, json.dumps(execution.to_dict(), ensure_ascii=False))
        self.assertNotIn("note.txt", json.dumps(execution.evidence, ensure_ascii=False))
        self.assertEqual(execution.evidence["after_source"]["size"], len(secret.encode("utf-8")))

    def test_preexisting_folder_is_not_claimed_as_new_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "existing"
            target.mkdir()
            args = {"action": "create_folder", "path": str(root), "name": "existing"}
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                raw = file_controller(args)
                execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.delivered)
        self.assertFalse(execution.verified)

    def test_write_reloads_file_and_verifies_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "data.txt"
            target.write_text("before", encoding="utf-8")
            args = {"action": "write", "path": str(target), "content": "after"}
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                raw = file_controller(args)
                execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertEqual(execution.evidence["after_source"]["size"], 5)

    def test_append_verifies_size_and_exact_tail_without_exposing_content(self):
        secret = "-private-tail"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "append.txt"
            target.write_text("before", encoding="utf-8")
            args = {"action": "write", "path": str(target), "content": secret, "append": True}
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                raw = file_controller(args)
                execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertTrue(execution.evidence["appended_content_match"])
        self.assertNotIn(secret, json.dumps(execution.to_dict(), ensure_ascii=False))

    def test_sampled_digest_matches_large_file_algorithm(self):
        payload = b"0123456789abcdef"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "large.bin"
            target.write_bytes(payload)
            with patch("core.file_postconditions._FILE_HASH_LIMIT", 8), \
                 patch("core.file_postconditions._FILE_SAMPLE_SIZE", 4):
                expected = _payload_digest(payload)
                observed = _file_digest(target, len(payload))

        self.assertEqual(observed, expected)

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
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
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
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                raw = file_controller(args)
                execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)
        self.assertTrue(execution.evidence["after_destination"]["exists"])

    def test_empty_file_copy_is_verified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "empty.txt"
            source.write_bytes(b"")
            destination = root / "copy.txt"
            args = {"action": "copy", "path": str(source), "destination": str(destination)}
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                raw = file_controller(args)
                execution = verify_postcondition("file_controller", args, raw, before_state=before)

        self.assertTrue(execution.can_claim_success)

    def test_delete_requires_source_to_disappear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "delete-me.txt"
            target.write_text("payload", encoding="utf-8")
            args = {"action": "delete", "path": str(target)}
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                target.unlink()
                execution = verify_file_postcondition(args, before_state=before, delivered=True)

        self.assertTrue(execution.can_claim_success)

    def test_unchanged_delete_remains_unverified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "keep-me.txt"
            target.write_text("payload", encoding="utf-8")
            args = {"action": "delete", "path": str(target)}
            with patch("actions.file_controller._SAFE_ROOTS", [root]):
                before = capture_file_state(args)
                execution = verify_file_postcondition(args, before_state=before, delivered=True)

        self.assertFalse(execution.verified)
        self.assertTrue(execution.delivered)

    def test_verifier_does_not_inspect_paths_outside_controller_safety_roots(self):
        with tempfile.TemporaryDirectory() as allowed_dir, tempfile.TemporaryDirectory() as blocked_dir:
            allowed = Path(allowed_dir)
            blocked = Path(blocked_dir)
            secret = blocked / "secret.txt"
            secret.write_text("sensitive", encoding="utf-8")
            args = {"action": "write", "path": str(secret), "content": "replacement"}

            with patch("actions.file_controller._SAFE_ROOTS", [allowed]):
                state = capture_file_state(args)

        self.assertFalse(state["source"]["resolvable"])
        self.assertNotIn("sha256", state["source"])
        self.assertNotIn("size", state["source"])


if __name__ == "__main__":
    unittest.main()
