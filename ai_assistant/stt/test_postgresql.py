"""PostgreSQL-only integration evidence; provider is always a Mock."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from queue import Queue
import time
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction, DatabaseError
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from . import ledger, normalizer
from .models import STTAccount, STTPeriod, STTReservation, STTPeriodBinding


class PostgreSQLTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.user = get_user_model().objects.create_user(username='pg-owner')
        now = timezone.now()
        self.period = ledger.VerifiedPeriod(self.user.pk, 'premium', now - timedelta(days=1),
                                           now + timedelta(days=1), 'pg-cycle')

    def reserve(self, period=None):
        return ledger.reserve(
            period=period or self.period, request_id=uuid4(),
            duration_ms=1001, audio_sha256='a' * 64, assistant_id=101)

    def send(self, row, provider):
        # Test-only illustration of the ledger's required calling contract.
        if ledger.claim_dispatch(user_id=self.user.pk, reservation_id=row.pk):
            return provider()

    def test_commit_is_visible_on_independent_connection_before_mock_provider(self):
        row = self.reserve()
        def provider_check():
            self.assertFalse(connection.in_atomic_block)
            def observe():
                try:
                    saved = STTReservation.objects.get(pk=row.pk)
                    return saved.state, saved.period.reserved_ms
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(1) as pool:
                self.assertEqual(pool.submit(observe).result(timeout=10), ('dispatched', 60_000))
        provider = Mock(side_effect=provider_check)
        self.send(row, provider)
        self.send(row, provider)
        provider.assert_called_once()
        ledger.settle(user_id=self.user.pk, reservation_id=row.pk, outcome='success')
        self.assertEqual(STTPeriod.objects.get(pk=row.period_id).used_ms, 60_000)

    def test_actual_database_error_after_dispatch_update_rolls_back_no_provider(self):
        row = self.reserve()
        provider = Mock()
        original = STTReservation.save
        def fail(saved, *args, **kwargs):
            original(saved, *args, **kwargs)
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1 / 0')
        with patch.object(STTReservation, 'save', fail), self.assertRaises(DatabaseError):
            self.send(row, provider)
        provider.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, 'reserved')
        self.assertEqual(STTPeriod.objects.get(pk=row.period_id).reserved_ms, 60_000)

    def test_commit_failure_does_not_dispatch(self):
        row = self.reserve()
        provider = Mock()
        with patch.object(connection, 'commit', side_effect=DatabaseError('injected commit failure')):
            with self.assertRaises(DatabaseError):
                self.send(row, provider)
        provider.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, 'reserved')

    def test_reservation_rollback_cannot_reach_provider(self):
        provider = Mock()
        original = STTReservation.save
        def fail(saved, *args, **kwargs):
            original(saved, *args, **kwargs)
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1 / 0')
        with patch.object(STTReservation, 'save', fail), self.assertRaises(DatabaseError):
            self.send(self.reserve(), provider)
        provider.assert_not_called()
        self.assertEqual(STTReservation.objects.count(), 0)
        self.assertEqual(STTPeriod.objects.count(), 0)

    def test_enclosing_transaction_rejects_dispatch_even_when_rolled_back(self):
        row = self.reserve()
        provider = Mock()
        with self.assertRaises(ledger.LedgerError):
            with transaction.atomic():
                self.send(row, provider)
        provider.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, 'reserved')

    def expired_lock_wait(self, operation):
        # No clock mocking: PostgreSQL reports an actual waiting backend and the
        # lock is kept until wall time passes the period end.
        period = replace(self.period, ends_at=timezone.now() + timedelta(seconds=3))
        evidence = normalizer.ServerPeriodEvidence(self.user.pk, 'stripe', 'sandbox',
            'test-sub', 'test-cycle', 'premium', period.starts_at, period.ends_at,
            timezone.now(), True, True, 'ordinary_monthly')
        if operation == 'claim':
            row = normalizer.reserve_normalized(evidence=evidence, request_id=uuid4(), duration_ms=1001, audio_sha256='a' * 64, assistant_id=101)
        else:
            STTAccount.objects.create(user=self.user)
        ready = Queue()
        provider = Mock()
        def worker():
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    ready.put(cursor.fetchone()[0])
                if operation == 'reserve':
                    self.reserve(period)
                elif operation == 'normalize':
                    normalizer.reserve_normalized(evidence=evidence, request_id=uuid4(), duration_ms=1001, audio_sha256='a' * 64, assistant_id=101)
                elif normalizer.claim_normalized(evidence=evidence, reservation_id=row.pk):
                    provider()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(1) as pool:
            with transaction.atomic():
                STTAccount.objects.select_for_update().get(user=self.user)
                future = pool.submit(worker)
                pid = ready.get(timeout=5)
                observed = False
                while timezone.now() < period.ends_at:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_stat_clear_snapshot()')
                        cursor.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s', [pid])
                        observed = cursor.fetchone()[0] == 'Lock'
                    if observed:
                        break
                    time.sleep(.02)
                self.assertTrue(observed, 'No real PostgreSQL lock wait observed before expiry')
                self.assertFalse(future.done())
                time.sleep(max(0, (period.ends_at - timezone.now()).total_seconds()) + .1)
            with self.assertRaises(ledger.InvalidPeriod):
                future.result(timeout=10)
        provider.assert_not_called()
        if operation == 'claim':
            row.refresh_from_db()
            self.assertEqual(row.state, 'reserved')
        else:
            self.assertEqual(STTReservation.objects.count(), 0)
            self.assertEqual(STTPeriodBinding.objects.count(), 0)
        print('Observed PostgreSQL Lock wait across real expiry:', operation)

    def test_real_reservation_lock_wait_across_period_end(self):
        self.expired_lock_wait('reserve')

    def test_real_normalizer_lock_wait_across_period_end(self):
        self.expired_lock_wait('normalize')

    def test_real_dispatch_lock_wait_across_period_end(self):
        self.expired_lock_wait('claim')


class PostgreSQLMigrationTests(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate([('u6_stt', target)])
        return MigrationExecutor(connection).loader.project_state([('u6_stt', target)]).apps if target else None

    def tearDown(self):
        self.migrate('0004_sttreservation_assistant_id_and_more')
        super().tearDown()

    def test_clean_migrations(self):
        self.migrate(None)
        self.assertFalse(any(name.startswith('u6_stt_') for name in connection.introspection.table_names()))
        self.migrate('0004_sttreservation_assistant_id_and_more')
        tables = connection.introspection.table_names()
        for model in (STTAccount, STTPeriod, STTReservation, STTPeriodBinding):
            self.assertIn(model._meta.db_table, tables)

    def test_0001_to_0002_preserves_all_existing_row_fields(self):
        apps = self.migrate('0001_initial')
        user = get_user_model().objects.create_user(username='migration-owner')
        account = apps.get_model('u6_stt', 'STTAccount').objects.create(user_id=user.pk, lock_version=7)
        period = apps.get_model('u6_stt', 'STTPeriod').objects.create(account=account,
            starts_at=timezone.now() - timedelta(days=1), ends_at=timezone.now() + timedelta(days=1),
            verification_ref='preserve', used_ms=6001, reserved_ms=3003)
        reservations = apps.get_model('u6_stt', 'STTReservation')
        for state, duration in [('consumed', 6001), ('reserved', 1001), ('dispatched', 1001), ('uncertain', 1001), ('released', 1001)]:
            reservations.objects.create(account=account, period=period, request_id=uuid4(), duration_ms=duration, state=state)
        names = ('STTAccount', 'STTPeriod', 'STTReservation')
        before = {name: list(apps.get_model('u6_stt', name).objects.order_by('pk').values()) for name in names}
        after = self.migrate('0002_sttperiodbinding')
        for name in names:
            self.assertEqual(before[name], list(after.get_model('u6_stt', name).objects.order_by('pk').values()))
        self.assertEqual(STTPeriodBinding.objects.count(), 0)
        STTPeriodBinding.objects.create(identity='a' * 64, period_id=period.pk, plan='premium')
        self.assertEqual(STTPeriodBinding.objects.count(), 1)
