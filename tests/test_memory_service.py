import unittest

from memory.domain import (
    DEFAULT_CONFIDENCE,
    MemoryRecord,
    MemoryState,
    MemoryType,
    SourceKind,
    STRONG_PREFERENCE_CONFIDENCE,
)
from memory.repository import InMemoryMemoryRepository
from memory.service import MemoryService


def _service(clock=None) -> tuple[MemoryService, InMemoryMemoryRepository]:
    repo = InMemoryMemoryRepository()
    return MemoryService(repo, clock=clock), repo


class MemoryLifecycleTests(unittest.TestCase):
    def test_propose_never_activates_by_itself(self):
        service, _ = _service()
        record = service.propose(owner_id="u1", type_="semantic", title="Editor", content="Usa VS Code")
        self.assertEqual(record.state, MemoryState.PROPOSED)
        self.assertEqual(record.confidence, DEFAULT_CONFIDENCE)

    def test_approve_activates_and_invalid_transitions_fail_closed(self):
        service, _ = _service()
        record = service.propose(owner_id="u1", type_="semantic", title="Editor", content="VS Code")
        approved = service.approve(record.id, owner_id="u1")
        self.assertEqual(approved.state, MemoryState.ACTIVE)
        with self.assertRaises(ValueError):
            service.approve(record.id, owner_id="u1")  # already active

    def test_archived_memory_only_returns_via_explicit_state(self):
        service, _ = _service()
        record = service.approve(
            service.propose(owner_id="u1", type_="semantic", title="Editor", content="VS Code").id,
            owner_id="u1",
        )
        service.archive(record.id, owner_id="u1")
        self.assertEqual(service.retrieve(owner_id="u1", text="VS Code"), [])
        restored = service.restore(record.id, owner_id="u1")
        self.assertEqual(restored.state, MemoryState.PROPOSED)  # back to review, not active


class IsolationTests(unittest.TestCase):
    def test_owner_isolation_is_hard(self):
        service, _ = _service()
        record = service.approve(
            service.propose(owner_id="u1", type_="semantic", title="Editor", content="VS Code").id,
            owner_id="u1",
        )
        self.assertEqual(service.retrieve(owner_id="u2"), [])
        with self.assertRaises(KeyError):
            service.archive(record.id, owner_id="u2")
        self.assertFalse(service.forget(record.id, owner_id="u2"))

    def test_project_isolation(self):
        service, _ = _service()
        service.approve(
            service.propose(
                owner_id="u1", type_="project", title="Deploy", content="Deploy via script",
                project_id="eutaktos",
            ).id,
            owner_id="u1",
        )
        hits = service.retrieve(owner_id="u1", project_id="antonella", text="Deploy")
        self.assertEqual(hits, [])
        hits_same = service.retrieve(owner_id="u1", project_id="eutaktos", text="Deploy")
        self.assertEqual(len(hits_same), 1)


class ConflictAndSupersessionTests(unittest.TestCase):
    def test_conflicting_subject_never_overwrites_silently(self):
        service, _ = _service()
        first = service.approve(
            service.propose(owner_id="u1", type_="semantic", title="Editor", content="Usa VS Code", subject="editor de código").id,
            owner_id="u1",
        )
        second = service.propose(
            owner_id="u1", type_="semantic", title="Editor", content="Usa Vim", subject="editor de código"
        )
        self.assertEqual(second.state, MemoryState.PROPOSED)
        self.assertEqual(second.conflict_with_id, first.id)
        # Both exist; nothing was overwritten.
        self.assertEqual(len(service.retrieve(owner_id="u1", text="")), 1)

    def test_explicit_supersession_retires_old_on_approve(self):
        service, _ = _service()
        first = service.approve(
            service.propose(owner_id="u1", type_="semantic", title="Editor", content="VS Code", subject="editor").id,
            owner_id="u1",
        )
        proposal = service.supersede(first.id, owner_id="u1", content="Agora usa Neovim")
        self.assertEqual(proposal.version, 2)
        self.assertEqual(proposal.supersedes_id, first.id)
        approved = service.approve(proposal.id, owner_id="u1")
        self.assertEqual(approved.state, MemoryState.ACTIVE)
        old = service.explain_source(approved.id, owner_id="u1")
        self.assertEqual(old["chain"][0]["version"], 2)
        self.assertEqual(old["chain"][1]["state"], "superseded")
        active = service.retrieve(owner_id="u1", text="Neovim")
        self.assertEqual(len(active), 1)

    def test_duplicate_proposals_are_stored_not_merged(self):
        service, _ = _service()
        first = service.propose(owner_id="u1", type_="semantic", title="X", content="conteúdo")
        second = service.propose(owner_id="u1", type_="semantic", title="X", content="conteúdo")
        self.assertNotEqual(first.id, second.id)  # explicit records; dedup is a review decision


class TtlTests(unittest.TestCase):
    def test_expired_memory_is_not_retrieved_and_expire_archives_it(self):
        service, _ = _service(clock=lambda: 1000.0)
        record = service.approve(
            service.propose(
                owner_id="u1", type_="episodic", title="Localização", content="Esta semana em Lisboa",
                expires_at=1100.0,
            ).id,
            owner_id="u1",
        )
        self.assertEqual(len(service.retrieve(owner_id="u1", now=1050.0)), 1)
        self.assertEqual(service.retrieve(owner_id="u1", now=1200.0), [])  # silently out of budget
        expired = service.expire(owner_id="u1", now=1200.0)
        self.assertEqual(expired, [record.id])
        after = service.explain_source(record.id, owner_id="u1")
        self.assertEqual(after["chain"][0]["state"], "archived")


class PreferenceTests(unittest.TestCase):
    def test_single_observation_is_never_a_strong_preference(self):
        service, _ = _service()
        weak = service.propose(
            owner_id="u1", type_="feedback", title="Música", content="Prefiro ouvir lofi quando programo"
        )
        service.approve(weak.id, owner_id="u1")
        self.assertEqual(service.strong_preferences(owner_id="u1"), [])

        confirmed = service.supersede(weak.id, owner_id="u1", content="Prefiro lofi (confirmado)", confidence=0.9)
        service.approve(confirmed.id, owner_id="u1")
        strong = service.strong_preferences(owner_id="u1")
        self.assertEqual(len(strong), 1)
        self.assertEqual(strong[0].confidence, 0.9)


class RetrievalBudgetTests(unittest.TestCase):
    def test_top_k_bounds_and_ordering(self):
        service, _ = _service()
        for index in range(5):
            service.approve(
                service.propose(
                    owner_id="u1", type_="semantic", title=f"facto {index}", content=f"facto {index}",
                    confidence=0.2 + index * 0.1,
                ).id,
                owner_id="u1",
            )
        hits = service.retrieve(owner_id="u1", top_k=3)
        self.assertEqual(len(hits), 3)
        confidences = [hit.record.confidence for hit in hits]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    def test_external_content_is_flagged_and_payload_is_bounded(self):
        service, _ = _service()
        long_tail = " detalhe sintético" * 40  # far beyond the 280-char budget
        record = service.approve(
            service.propose(
                owner_id="u1", type_="semantic", title="Preço", content="O preço é X." + long_tail,
                source_kind=SourceKind.EXTERNAL, source_ref="https://exemplo.local",
            ).id,
            owner_id="u1",
        )
        hit = service.retrieve(owner_id="u1", text="preço")[0]
        self.assertTrue(hit.is_external)
        payload = hit.as_prompt_payload()
        self.assertTrue(payload["external_information"])
        self.assertLessEqual(len(payload["summary"]), 280)  # bounded prompt payload
        self.assertNotIn(long_tail, payload["summary"])


class DomainModelTests(unittest.TestCase):
    def test_confidence_is_bounded(self):
        record = MemoryRecord(id="a", owner_id="u1", type="semantic", title="t", content="c", confidence=5)
        self.assertEqual(record.confidence, 1.0)

    def test_to_dict_has_no_secret_fields(self):
        forbidden = {"api_key", "password", "token", "clipboard", "cookie"}
        record = MemoryRecord(id="a", owner_id="u1", type="semantic", title="t", content="c")
        self.assertTrue(set(record.to_dict()).isdisjoint(forbidden))


if __name__ == "__main__":
    unittest.main()
