from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import time
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction, DatabaseError
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from . import authorization, service
from .errors import AuthorizationDenied
from .models import TTSAccount, TTSRequest
from .provider import MockProvider


class PostgreSQLTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.user = get_user_model().objects.create_user(username='pg-owner')

    def test_fresh_migration_and_schema(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('u62_tts', None)])
        self.assertNotIn(TTSRequest._meta.db_table, connection.introspection.table_names())
        try:
            MigrationExecutor(connection).migrate([('u62_tts', '0001_initial')])
            self.assertIn(TTSRequest._meta.db_table, connection.introspection.table_names())
            self.assertEqual(TTSRequest.objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate([('u62_tts', '0002_audio_storage')])

    def test_actual_sql_failure_rolls_back_claim_without_dispatch(self):
        with patch.object(authorization, '_effective_plan', return_value='premium'), \
                patch.object(authorization, '_owns_assistant', return_value=True):
            args = dict(user=self.user, assistant_id=7, text='Hej', request_id=uuid4())
            row = service.prepare(**args)
            original = TTSRequest.save
            def fail(saved, *a, **kw):
                original(saved, *a, **kw)
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1 / 0')
            with patch.object(TTSRequest, 'save', fail), patch.object(MockProvider, 'synthesize') as provider:
                with self.assertRaises(DatabaseError):
                    service.synthesize(**args)
                provider.assert_not_called()
            row.refresh_from_db()
            self.assertEqual(row.state, 'pending')

    def test_revocation_committed_during_real_lock_wait_blocks_claim(self):
        with patch.object(authorization, '_effective_plan', return_value='premium'), \
                patch.object(authorization, '_owns_assistant', return_value=True):
            row = service.prepare(user=self.user, assistant_id=7, text='Hej', request_id=uuid4())
            ready = Queue()
            def worker():
                try:
                    with connections['default'].cursor() as cursor:
                        cursor.execute('SELECT pg_backend_pid()')
                        ready.put(cursor.fetchone()[0])
                    return service.claim(user=self.user, assistant_id=7, row_id=row.pk)
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(1) as pool:
                with transaction.atomic():
                    TTSAccount.objects.select_for_update().get(user=self.user)
                    future = pool.submit(worker)
                    pid = ready.get(timeout=5)
                    deadline = time.monotonic() + 5
                    observed = False
                    while time.monotonic() < deadline:
                        with connection.cursor() as cursor:
                            cursor.execute('SELECT pg_stat_clear_snapshot()')
                            cursor.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s', [pid])
                            observed = cursor.fetchone()[0] == 'Lock'
                        if observed:
                            break
                        time.sleep(.02)
                    self.assertTrue(observed, 'Expected real PostgreSQL lock wait')
                    get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
                with self.assertRaises(AuthorizationDenied):
                    future.result(timeout=10)
            row.refresh_from_db()
            self.assertEqual(row.state, 'pending')
