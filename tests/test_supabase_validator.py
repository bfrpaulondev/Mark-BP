"""Exercise validator sequencing/failure paths with a strict Data API fake.

These tests prove client behavior, not physical Postgres RLS deployment.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from scripts import validate_supabase_memory as validator
from test_memory_bootstrap_security import OWNER, OTHER, env, jwt


class Denied(RuntimeError):
    code = '42501'


class Table:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.op, self.payload, self.filters, self.cap = 'select', None, [], None
    def select(self, fields):
        self.client.selections.append((self.table, fields))
        if self.client.missing_schema and 'metadata' in fields: raise RuntimeError('missing column')
        return self
    def eq(self, name, value): self.filters.append((name, value)); return self
    def limit(self, cap): self.cap = cap; return self
    def upsert(self, payload): self.op, self.payload = 'upsert', payload; return self
    def insert(self, payload): self.op, self.payload = 'insert', payload; return self
    def update(self, payload): self.op, self.payload = 'update', payload; return self
    def delete(self): self.op = 'delete'; return self
    def execute(self):
        rows = self.client.rows
        visible = [r for r in rows.values() if r['owner_id'] == self.client.owner and all(r.get(k) == v for k,v in self.filters)]
        if self.op in ('upsert', 'insert'):
            payload = dict(self.payload)
            if payload['owner_id'] != self.client.owner:
                if self.client.auth_timeout: raise TimeoutError('fixture secret')
                raise Denied('fixture secret')
            for field in ('created_at', 'updated_at', 'archived_at', 'approved_at'):
                if payload.get(field) is not None and not isinstance(payload[field], str):
                    raise ValueError('timestamptz must be serialized')
            rows[payload['id']] = payload
            if self.client.fail_after_write:
                self.client.fail_after_write = False
                raise TimeoutError('write committed but response lost')
            return NS(data=[payload])
        if self.op == 'update':
            for row in visible: row.update(self.payload)
        if self.op == 'delete':
            if self.client.fail_cleanup: raise RuntimeError('cleanup failed secret')
            for row in visible: rows.pop(row['id'])
        if self.cap is not None: visible = visible[:self.cap]
        return NS(data=[dict(row) for row in visible])


class Client:
    def __init__(self, owner, rows):
        self.owner, self.rows = owner, rows
        self.selections = []
        self.missing_schema = self.fail_after_write = self.fail_cleanup = self.auth_timeout = False
        self.auth = NS(get_session=lambda: NS(access_token=jwt(subject=owner)),
                       get_user=lambda token: NS(user=NS(id=owner, is_anonymous=False)))
    def table(self, name): return Table(self, name)


class ValidatorTests(unittest.TestCase):
    def run_validation(self, *, second=False, missing=False, write_failure=False, cleanup_failure=False, auth_timeout=False):
        rows = {}
        primary, secondary = Client(OWNER, rows), Client(OTHER, rows)
        primary.missing_schema = missing
        primary.fail_after_write = write_failure
        primary.fail_cleanup = cleanup_failure
        primary.auth_timeout = auth_timeout
        values = env()
        if second:
            values.update({key.replace('ANTONELLA_SUPABASE', 'ANTONELLA_SUPABASE_TEST_B'): value for key, value in env().items()})
        with patch.dict(os.environ, values, clear=True), patch.object(validator, 'client_from_env', side_effect=lambda prefix: secondary if prefix.endswith('TEST_B') else primary):
            report = validator.validate()
        self.assertNotIn('secret', json.dumps(report))
        return report, rows, primary

    def test_missing_configuration_still_respects_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'custom' / 'report.json'
            with patch.dict(os.environ, {}, clear=True), patch('sys.argv', ['validate', '--output', str(output)]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(validator.main(), 0)
            self.assertEqual(json.loads(output.read_text())['status'], 'NOT CONFIGURED')

    def test_lifecycle_timestamps_archive_and_cleanup(self):
        report, rows, primary = self.run_validation()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['rls'], 'NOT TESTED')
        self.assertEqual(rows, {})
        self.assertIn('archive-read-back', [s['step'] for s in report['steps']])
        self.assertEqual({t for t,f in primary.selections}, {'memories','memory_feedback','memory_relations'})

    def test_missing_metadata_migration_fails_before_insert(self):
        report, rows, _ = self.run_validation(missing=True)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(rows, {})

    def test_response_lost_after_commit_still_cleans_known_id(self):
        report, rows, _ = self.run_validation(write_failure=True)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(rows, {})
        self.assertIn({'step': 'cleanup-read-back', 'status': 'PASS'}, report['steps'])

    def test_cleanup_error_fails_report(self):
        report, rows, _ = self.run_validation(cleanup_failure=True)
        self.assertEqual(report['status'], 'FAIL')
        self.assertTrue(rows)
        self.assertTrue(any(s['step'] == 'cleanup-read-back' and s['status'] == 'FAIL' for s in report['steps']))

    def test_two_user_rls_checks_include_denied_cross_owner_writes(self):
        report, rows, _ = self.run_validation(second=True)
        self.assertEqual(report['status'], 'PASS')
        self.assertTrue(report['rls'].startswith('PASS: memories'))
        self.assertEqual(rows, {})

    def test_network_error_is_never_rls_proof(self):
        report, rows, _ = self.run_validation(second=True, auth_timeout=True)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['rls'], 'NOT TESTED')
        self.assertEqual(rows, {})

    def test_same_authenticated_owner_is_not_rls_proof(self):
        values = env(); values['ANTONELLA_SUPABASE_TEST_B_URL'] = values['ANTONELLA_SUPABASE_URL']
        c = Client(OWNER, {})
        with patch.dict(os.environ, values, clear=True), patch.object(validator, 'client_from_env', return_value=c):
            report = validator.validate()
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['rls'], 'NOT TESTED')
        self.assertEqual(c.rows, {})
