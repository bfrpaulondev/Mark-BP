import unittest
from datetime import datetime, timezone

from memory.domain import MemoryRecord, MemoryType
from memory.supabase_adapter import _payload_for_db, _timestamp_from_db


class SupabaseAdapterRealShapeTests(unittest.TestCase):
    def test_postgrest_iso_timestamp_becomes_epoch(self):
        value = _timestamp_from_db("2026-09-06T08:00:00.000000+00:00")
        expected = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(value, expected)

    def test_z_timestamp_becomes_epoch(self):
        value = _timestamp_from_db("2026-09-06T08:00:00Z")
        expected = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(value, expected)

    def test_invalid_timestamp_fails_closed(self):
        with self.assertRaises(ValueError):
            _timestamp_from_db("not-a-timestamp")

    def test_payload_serializes_epochs_as_timestamptz_and_keeps_metadata(self):
        epoch = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc).timestamp()
        record = MemoryRecord(
            id="a" * 32,
            owner_id="11111111-1111-1111-1111-111111111111",
            type=MemoryType.SEMANTIC,
            title="Editor",
            content="VS Code",
            created_at=epoch,
            updated_at=epoch,
            expires_at=epoch + 60,
            metadata={"expired": False, "source_count": 2},
        )

        payload = _payload_for_db(record)

        self.assertEqual(payload["created_at"], "2026-09-06T08:00:00Z")
        self.assertEqual(payload["updated_at"], "2026-09-06T08:00:00Z")
        self.assertEqual(payload["expires_at"], "2026-09-06T08:01:00Z")
        self.assertEqual(payload["metadata"], {"expired": False, "source_count": 2})


if __name__ == "__main__":
    unittest.main()
