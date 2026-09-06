import unittest

from memory.domain import MemoryRecord, MemoryState, MemoryType
from memory.repository import MemoryQuery
from memory.service import MemoryService
from memory.supabase_adapter import (
    ENV_KEY,
    ENV_URL,
    SupabaseConfigurationError,
    SupabaseMemoryRepository,
)


class FakeTable:
    """Minimal supabase-py fluent API over in-memory rows."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: list[tuple[str, str, object]] = []
        self._limit: int | None = None
        self._pending: dict | None = None

    def _chain(self):
        return self

    # building
    def select(self, *_cols):
        return self._chain()

    def insert(self, payload, *_a, **_kw):
        self._pending = dict(payload)
        return self._chain()

    def upsert(self, payload, *_a, **_kw):
        self._pending = dict(payload)
        return self._chain()

    def delete(self):
        self._pending = {"__delete__": True}
        return self._chain()

    def eq(self, column: str, value):
        self._filters.append((column, "==", value))
        return self._chain()

    def limit(self, count: int):
        self._limit = count
        return self._chain()

    def execute(self):
        rows = [dict(r) for r in self._rows]
        for column, op, value in self._filters:
            rows = [r for r in rows if r.get(column) == value]
        if self._limit is not None:
            rows = rows[: self._limit]
        if self._pending is not None:
            if self._pending.get("__delete__"):
                keys = [r["id"] for r in rows]
                self._rows[:] = [r for r in self._rows if r["id"] not in keys]
            else:
                payload = dict(self._pending)
                for index, row in enumerate(self._rows):
                    if row["id"] == payload.get("id"):
                        self._rows[index] = payload
                        break
                else:
                    self._rows.append(payload)
        self._filters = []
        self._limit = None
        self._pending = None
        return type("Response", (), {"data": rows})()


class FakeSupabaseClient:
    def __init__(self):
        self._rows: list[dict] = []
        self._tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeTable:
        if name not in self._tables:
            self._tables[name] = FakeTable(self._rows)
        return self._tables[name]


def _record(**overrides) -> MemoryRecord:
    payload = dict(
        id="rec-1",
        owner_id="u1",
        type="semantic",
        title="Editor",
        content="Usa VS Code",
        state="active",
        confidence=0.8,
    )
    payload.update(overrides)
    return MemoryRecord(**payload)


class SupabaseAdapterTests(unittest.TestCase):
    def setUp(self):
        self.repo = SupabaseMemoryRepository(FakeSupabaseClient())

    def test_save_and_get_round_trip(self):
        self.repo.save(_record())
        loaded = self.repo.get("rec-1", "u1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.type, MemoryType.SEMANTIC)
        self.assertEqual(loaded.state, MemoryState.ACTIVE)
        self.assertEqual(loaded.confidence, 0.8)

    def test_get_is_owner_isolated(self):
        self.repo.save(_record())
        self.assertIsNone(self.repo.get("rec-1", "u2"))

    def test_query_filters_owner_state_type_and_text(self):
        self.repo.save(_record())
        self.repo.save(_record(id="rec-2", state="proposed"))
        self.repo.save(_record(id="rec-3", title="Outro", content="Vim", owner_id="u2"))
        hits = self.repo.query(MemoryQuery(owner_id="u1", state=MemoryState.ACTIVE, text="vs code"))
        self.assertEqual([r.id for r in hits], ["rec-1"])

    def test_query_orders_by_confidence_then_recency(self):
        self.repo.save(_record(id="a", confidence=0.4, updated_at=1.0))
        self.repo.save(_record(id="b", confidence=0.9, updated_at=2.0))
        self.repo.save(_record(id="c", confidence=0.9, updated_at=3.0))
        hits = self.repo.query(MemoryQuery(owner_id="u1"))
        self.assertEqual([r.id for r in hits], ["c", "b", "a"])

    def test_query_skips_expired_records(self):
        self.repo.save(_record(id="old", expires_at=100.0))
        self.assertEqual(self.repo.query(MemoryQuery(owner_id="u1", now=200.0)), [])
        self.assertEqual(len(self.repo.query(MemoryQuery(owner_id="u1", now=50.0))), 1)

    def test_query_applies_row_cap(self):
        for index in range(4):
            self.repo.save(_record(id=f"r{index}", title=f"t{index}", content=f"c{index}"))
        hits = self.repo.query(MemoryQuery(owner_id="u1"))
        self.assertEqual(len(hits), 4)  # under the 500-row adapter cap

    def test_delete_is_owner_isolated(self):
        self.repo.save(_record())
        self.assertFalse(self.repo.delete("rec-1", "u2"))
        self.assertTrue(self.repo.delete("rec-1", "u1"))
        self.assertIsNone(self.repo.get("rec-1", "u1"))

    def test_service_works_over_the_adapter(self):
        service = MemoryService(self.repo)
        approved = service.approve(
            service.propose(owner_id="u1", type_="semantic", title="Editor", content="VS Code").id,
            owner_id="u1",
        )
        hits = service.retrieve(owner_id="u1", text="code")
        self.assertEqual(hits[0].record.id, approved.id)


class SupabaseConfigurationTests(unittest.TestCase):
    def test_missing_env_fails_closed(self):
        import os

        saved = (os.environ.get(ENV_URL), os.environ.get(ENV_KEY))
        os.environ.pop(ENV_URL, None)
        os.environ.pop(ENV_KEY, None)
        try:
            with self.assertRaises(SupabaseConfigurationError):
                __import__("memory.supabase_adapter", fromlist=["client_from_env"]).client_from_env()
        finally:
            if saved[0]:
                os.environ[ENV_URL] = saved[0]
            if saved[1]:
                os.environ[ENV_KEY] = saved[1]

    def test_env_names_are_stable(self):
        self.assertEqual(ENV_URL, "ANTONELLA_SUPABASE_URL")
        self.assertEqual(ENV_KEY, "ANTONELLA_SUPABASE_KEY")


if __name__ == "__main__":
    unittest.main()
