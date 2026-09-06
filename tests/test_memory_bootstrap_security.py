import base64
import json
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from memory.bootstrap import create_memory_stack
from memory.command_bridge import MemoryCommandBridge
from memory.domain import MemoryRecord
from memory.repository import MemoryQuery
from memory.supabase_adapter import (SupabaseConfigurationError, SupabaseMemoryRepository,
    authenticated_owner_id, client_from_env, verify_memory_schema)

OWNER = '11111111-1111-1111-1111-111111111111'
OTHER = '22222222-2222-2222-2222-222222222222'


def jwt(role='authenticated', subject=OWNER):
    return 'fixture.' + base64.urlsafe_b64encode(json.dumps({'role': role, 'sub': subject}).encode()).decode().rstrip('=') + '.signature'


def env():
    return {'ANTONELLA_SUPABASE_URL': 'https://fixture.supabase.co',
            'ANTONELLA_SUPABASE_KEY': 'sb_publishable_fixture',
            'ANTONELLA_SUPABASE_ACCESS_TOKEN': jwt(),
            'ANTONELLA_SUPABASE_REFRESH_TOKEN': 'fixture-refresh'}


def client():
    result = Mock()
    result.auth.get_session.return_value = NS(access_token=jwt())
    result.auth.get_user.return_value = NS(user=NS(id=OWNER, is_anonymous=False))
    return result


class BootstrapSecurityTests(unittest.TestCase):
    def test_absent_configuration_is_explicit_session_only(self):
        with patch.dict(os.environ, {}, clear=True):
            stack = create_memory_stack()
        self.assertEqual(stack.backend, 'inmemory')
        self.assertEqual(stack.status, 'NOT CONFIGURED')
        self.assertFalse(stack.persistent)
        result = MemoryCommandBridge(stack.service).handle('Aprende que uso Python')
        self.assertIn('apenas desta sessão', result['spoken'])
        self.assertFalse(result['persistent'])

    def test_partial_empty_or_failed_configuration_never_falls_back(self):
        for values in ({'ANTONELLA_SUPABASE_URL': ''}, {'ANTONELLA_SUPABASE_KEY': 'bad'}, env()):
            with patch.dict(os.environ, values, clear=True), patch('memory.bootstrap.client_from_env', side_effect=RuntimeError('private-token')):
                stack = create_memory_stack()
            self.assertEqual(stack.status, 'CONFIGURED BUT FAILED')
            self.assertIsNone(stack.repository)
            self.assertIsNone(stack.service)
            self.assertNotIn('private-token', repr(stack))
            self.assertEqual(MemoryCommandBridge(stack.service).handle('Aprende que uso Python')['status'], 'CONFIGURED BUT FAILED')
            self.assertIsNone(MemoryCommandBridge(stack.service).handle('abrir browser'))

    def test_schema_or_network_failure_is_not_ready(self):
        for error in (RuntimeError('schema secret'), TimeoutError('network secret')):
            with patch.dict(os.environ, env(), clear=True), patch('memory.bootstrap.client_from_env', return_value=client()), patch('memory.bootstrap.verify_memory_schema', side_effect=error):
                stack = create_memory_stack()
            self.assertFalse(stack.persistent)
            self.assertIsNone(stack.service)

    def test_ready_stack_binds_verified_owner(self):
        c = client()
        with patch.dict(os.environ, env(), clear=True), patch('memory.bootstrap.client_from_env', return_value=c):
            stack = create_memory_stack()
        self.assertEqual(stack.owner_id, OWNER)
        self.assertTrue(stack.persistent)
        self.assertEqual(stack.repository._owner_id, OWNER)
        self.assertEqual([call.args[0] for call in c.table.call_args_list], ['memories', 'memory_relations', 'memory_feedback'])
        selections = [call.args[0] for call in c.table.return_value.select.call_args_list]
        self.assertIn('metadata', selections[0])

    def test_runtime_operation_failure_does_not_claim_save_or_use_fallback(self):
        service = Mock()
        service.propose.side_effect = TimeoutError('secret')
        result = MemoryCommandBridge(service, owner_id=OWNER, backend='supabase', persistent=True).handle('Aprende que uso Python')
        self.assertEqual(result['status'], 'OPERATION FAILED')
        self.assertNotIn('secret', str(result))
        self.assertNotIn('proposal_id', result)


class AuthSecurityTests(unittest.TestCase):
    def test_session_installed_and_owner_verified_by_auth_server(self):
        c = client()
        factory = Mock(return_value=c)
        with patch.dict('sys.modules', {'supabase': NS(create_client=factory)}):
            self.assertIs(client_from_env(env=env()), c)
        c.auth.set_session.assert_called_once_with(jwt(), 'fixture-refresh')
        c.auth.get_user.assert_called_with(jwt())

    def test_privileged_keys_rejected_before_client_creation(self):
        for key in ('sb_secret_fixture', jwt('service_role'), jwt('authenticated'), 'bad'):
            values = env(); values['ANTONELLA_SUPABASE_KEY'] = key
            factory = Mock()
            with patch.dict('sys.modules', {'supabase': NS(create_client=factory)}), self.assertRaises(SupabaseConfigurationError):
                client_from_env(env=values)
            factory.assert_not_called()

    def test_legacy_anon_key_accepted_only_with_user_session(self):
        values = env(); values['ANTONELLA_SUPABASE_KEY'] = jwt('anon')
        with patch.dict('sys.modules', {'supabase': NS(create_client=lambda *args: client())}):
            self.assertIsNotNone(client_from_env(env=values))
        values.pop('ANTONELLA_SUPABASE_ACCESS_TOKEN')
        with self.assertRaises(SupabaseConfigurationError): client_from_env(env=values)

    def test_service_role_session_and_http_url_rejected(self):
        for field, value in (('ACCESS_TOKEN', jwt('service_role')), ('URL', 'http://fixture.supabase.co')):
            values = env(); values['ANTONELLA_SUPABASE_' + field] = value
            with self.assertRaises(SupabaseConfigurationError): client_from_env(env=values)

    def test_forged_local_owner_claim_does_not_authorize(self):
        c = client(); c.auth.get_user.return_value = NS(user=NS(id=OTHER, is_anonymous=False))
        with self.assertRaises(SupabaseConfigurationError): authenticated_owner_id(c)
        c.auth.get_user.side_effect = RuntimeError('revoked session')
        with self.assertRaises(RuntimeError): authenticated_owner_id(c)

    def test_local_or_anonymous_owner_rejected(self):
        for identity in (NS(id='local', is_anonymous=False), NS(id=OWNER, is_anonymous=True)):
            c = client(); c.auth.get_user.return_value = NS(user=identity)
            with self.assertRaises(SupabaseConfigurationError): authenticated_owner_id(c)

    def test_owner_mismatch_and_session_switch_fail_before_data_api(self):
        c = client(); repo = SupabaseMemoryRepository(c, owner_id=OWNER)
        for action in (lambda: repo.get('id', OTHER), lambda: repo.query(MemoryQuery(owner_id=OTHER)),
                lambda: repo.delete('id', OTHER), lambda: repo.save(MemoryRecord(id='id', owner_id=OTHER, type='semantic', title='t', content='c'))):
            with self.assertRaises(SupabaseConfigurationError): action()
        c.table.assert_not_called()
        c.auth.get_user.return_value = NS(user=NS(id=OTHER, is_anonymous=False))
        with self.assertRaises(SupabaseConfigurationError): repo.get('id', OWNER)
        c.table.assert_not_called()
