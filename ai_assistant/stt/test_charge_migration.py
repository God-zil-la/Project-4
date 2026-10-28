from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.exceptions import IrreversibleError
from django.test import TransactionTestCase
from django.utils import timezone

from .ledger import Conflict, VerifiedPeriod, reserve, settle
from .models import STTPeriod, STTReservation


class ChargeMigrationTests(TransactionTestCase):
    def migrate(self, name):
        executor = MigrationExecutor(connection)
        target = [('u6_stt', name)]
        executor.migrate(target)
        return MigrationExecutor(connection).loader.project_state(target).apps

    def tearDown(self):
        self.migrate('0004_sttreservation_assistant_id_and_more')
        super().tearDown()

    def test_old_holds_and_usage_preserved_then_settled_without_rounding_again(self):
        apps = self.migrate('0002_sttperiodbinding')
        user = get_user_model().objects.create_user(username='legacy-charge')
        account = apps.get_model('u6_stt', 'STTAccount').objects.create(user_id=user.pk)
        now = timezone.now()
        bucket = apps.get_model('u6_stt', 'STTPeriod').objects.create(account=account,
            starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=1),
            verification_ref='legacy', used_ms=1001, reserved_ms=3003)
        old = apps.get_model('u6_stt', 'STTReservation')
        rows = {state: old.objects.create(account=account, period=bucket, request_id=uuid4(),
                 duration_ms=1001, state=state)
                for state in ('reserved', 'dispatched', 'uncertain', 'consumed', 'released')}
        self.migrate('0004_sttreservation_assistant_id_and_more')
        self.assertEqual(set(STTReservation.objects.values_list('charge_ms', flat=True)), {1001})
        current = STTPeriod.objects.get(pk=bucket.pk)
        self.assertEqual((current.used_ms, current.reserved_ms), (1001, 3003))
        period = VerifiedPeriod(user.pk, 'premium', bucket.starts_at, bucket.ends_at, 'legacy')
        for state, row in rows.items():
            with self.assertRaises(Conflict):
                reserve(period=period, request_id=row.request_id, duration_ms=1001,
                        audio_sha256='a' * 64, assistant_id=101)
            outcome = 'not_processed' if state in ('reserved', 'released') else 'success'
            for _ in range(2):
                settle(user_id=user.pk, reservation_id=row.pk, outcome=outcome)
        fresh = reserve(period=period, request_id=uuid4(), duration_ms=10_000,
                        audio_sha256='a' * 64, assistant_id=101)
        current.refresh_from_db()
        self.assertEqual(fresh.charge_ms, 60_000)
        self.assertEqual((current.used_ms, current.reserved_ms), (3003, 60_000))

    def test_rollback_refuses_to_discard_rounded_charge(self):
        user = get_user_model().objects.create_user(username='rollback-charge')
        now = timezone.now()
        period = VerifiedPeriod(user.pk, 'premium', now - timedelta(days=1),
                                now + timedelta(days=1), 'rollback')
        row = reserve(period=period, request_id=uuid4(), duration_ms=10_000,
                      audio_sha256='a' * 64, assistant_id=101)
        with self.assertRaises(IrreversibleError):
            self.migrate('0002_sttperiodbinding')
        self.migrate('0004_sttreservation_assistant_id_and_more')
        self.assertEqual(STTReservation.objects.get(pk=row.pk).charge_ms, 60_000)
