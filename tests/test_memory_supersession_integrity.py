import unittest

from memory.domain import MemoryState, MemoryType
from memory.repository import InMemoryMemoryRepository
from memory.service import MemoryService


class MemorySupersessionIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryMemoryRepository()
        self.service = MemoryService(self.repo, clock=lambda: 1000.0)

    def _active(self, *, title="Editor", project_id="p1", type_=MemoryType.SEMANTIC):
        proposed = self.service.propose(
            owner_id="u1",
            project_id=project_id,
            type_=type_,
            title=title,
            content="old",
        )
        return self.service.approve(proposed.id, owner_id="u1")

    def test_arbitrary_active_memory_cannot_be_used_as_supersession_target(self):
        previous = self._active(title="Editor")

        with self.assertRaises(ValueError):
            self.service.propose(
                owner_id="u1",
                project_id="p1",
                type_=MemoryType.SEMANTIC,
                title="Browser",
                content="new",
                supersedes_id=previous.id,
            )

    def test_cross_project_supersession_is_rejected(self):
        previous = self._active(title="Editor", project_id="p1")

        with self.assertRaises(ValueError):
            self.service.propose(
                owner_id="u1",
                project_id="p2",
                type_=MemoryType.SEMANTIC,
                title="Editor",
                content="new",
                supersedes_id=previous.id,
            )

    def test_only_active_memories_can_be_superseded(self):
        proposed = self.service.propose(
            owner_id="u1",
            project_id="p1",
            type_=MemoryType.SEMANTIC,
            title="Editor",
            content="old",
        )

        with self.assertRaises(ValueError):
            self.service.supersede(proposed.id, owner_id="u1", content="new")

    def test_stale_supersession_fails_closed_at_approval(self):
        previous = self._active(title="Editor")
        candidate = self.service.supersede(previous.id, owner_id="u1", content="new")
        self.service.archive(previous.id, owner_id="u1")

        with self.assertRaises(ValueError):
            self.service.approve(candidate.id, owner_id="u1")

        stored = self.repo.get(candidate.id, "u1")
        self.assertEqual(stored.state, MemoryState.PROPOSED)


if __name__ == "__main__":
    unittest.main()
