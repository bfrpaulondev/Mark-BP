import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from memory.command_bridge import MemoryCommandBridge
from memory.domain import MemoryState, MemoryType
from memory.repository import InMemoryMemoryRepository
from memory.service import MemoryService


class MemoryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryMemoryRepository()
        self.service = MemoryService(self.repo)
        self.bridge = MemoryCommandBridge(self.service, owner_id='owner')

    def active(self, title, content, owner='owner', source='user'):
        proposal = self.service.propose(owner_id=owner, type_='semantic', title=title, content=content, source_kind=source)
        return self.service.approve(proposal.id, owner_id=owner)

    def test_procedure_is_proposal_never_auto_active(self):
        result = self.bridge.handle('Aprende como preencher relatório')
        row = self.repo.get(result['proposal_id'], 'owner')
        self.assertEqual(row.type, MemoryType.PROCEDURAL)
        self.assertEqual(row.state, MemoryState.PROPOSED)
        self.assertTrue(result['requires_approval'])
        self.assertEqual(self.service.retrieve(owner_id='owner'), [])

    def test_forget_only_identifies_target_and_never_mutates(self):
        row = self.active('Python', 'Python preference')
        with patch.object(self.service, 'archive', wraps=self.service.archive) as archive, patch.object(self.service, 'forget', wraps=self.service.forget) as forget:
            result = self.bridge.handle('Esquece Python')
        archive.assert_not_called(); forget.assert_not_called()
        self.assertEqual(result['target_id'], row.id)
        self.assertTrue(result['requires_approval'])
        self.assertEqual(self.repo.get(row.id, 'owner').state, MemoryState.ACTIVE)

    def test_list_and_explain_are_payload_and_owner_scoped(self):
        self.active('JavaScript', 'JS')
        row = self.active('Python', 'Python', source='external')
        self.active('Python private', 'Python', owner='other')
        result = self.bridge.handle('Mostra o que sabes sobre Python')
        self.assertIn('Python', result['spoken'])
        self.assertNotIn('JavaScript', result['spoken'])
        self.assertNotIn('private', result['spoken'])
        result = self.bridge.handle('De onde aprendeste Python')
        self.assertEqual(result['memory_id'], row.id)
        self.assertIn('external', result['spoken'])

    def test_one_execution_is_observed_once_by_actual_runtime_handler(self):
        from types import SimpleNamespace as NS
        from unittest.mock import Mock
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'antonella.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AntonellaLive')
        handler = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_on_text_command')
        execute = Mock(return_value=NS(verified=True))
        intent = NS(kind='status', args={})
        class ImmediateThread:
            def __init__(self, *, target, **kwargs): self.target = target
            def start(self): self.target()
        namespace = {'get_config': lambda: {}, 'parse_local_text_command': lambda text: intent,
                     'execute_local_intent': execute, 'threading': NS(Thread=ImmediateThread),
                     'local_command_feedback': lambda *args: NS(phrase_pt='Estado consultado.'),
                     '_SPOKEN_LOCAL_KINDS': frozenset()}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'antonella.py', 'exec'), namespace)
        engine = NS(memory_bridge=self.bridge, ui=NS(write_log=lambda *args: None,
                    set_state=lambda *args: None, muted=False), _session_log=[])
        namespace['_on_text_command'](engine, 'estado')
        execute.assert_called_once()
        self.assertEqual(len(self.bridge._observations), 1)
        self.assertEqual(self.bridge._observations[0].signature, 'local.status')

    def test_distinct_signatures_each_reach_suggestion(self):
        suggestions = []
        for index in range(3):
            for offset, signature in enumerate(('local.open_app', 'local.scroll')):
                with patch('memory.command_bridge.time.time', return_value=index * 10 + offset):
                    suggestions.append(self.bridge.observe(signature))
        self.assertEqual(sum(bool(s) for s in suggestions), 2)
        self.assertEqual(len(self.bridge._observations), 6)

    def test_duplicate_instrumentation_does_not_inflate_habits(self):
        with patch('memory.command_bridge.time.time', return_value=10):
            for _ in range(8): self.assertIsNone(self.bridge.observe('local.open_app'))
        self.assertEqual(len(self.bridge._observations), 1)
        with patch('memory.command_bridge.time.time', return_value=20):
            self.assertIsNone(self.bridge.observe('local.open_app'))
        with patch('memory.command_bridge.time.time', return_value=30):
            self.assertIsNotNone(self.bridge.observe('local.open_app'))
        self.assertEqual(len(self.bridge._observations), 3)
