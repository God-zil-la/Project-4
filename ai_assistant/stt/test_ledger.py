from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from .ledger import (Conflict, InvalidPeriod, LedgerError, QuotaExceeded,
                     VerifiedPeriod, claim_dispatch, reserve, settle)
from .models import STTAccount, STTPeriod, STTReservation


class LedgerTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='stt-owner')
        self.other = get_user_model().objects.create_user(username='other-owner')
        now = timezone.now()
        self.period = VerifiedPeriod(self.user.pk, 'premium', now - timedelta(days=15),
                                     now + timedelta(days=15), 'verified-month-1')

    def reserve(self, duration=1000, **overrides):
        return reserve(period=overrides.get('period', self.period),
                       request_id=overrides.get('request_id', uuid4()),
                       duration_ms=duration,
                       audio_sha256=overrides.get('audio_sha256', 'a' * 64),
                       assistant_id=overrides.get('assistant_id', 101))

    def dispatch(self, row):
        return claim_dispatch(user_id=self.user.pk, reservation_id=row.pk)

    def settle(self, row, outcome):
        return settle(user_id=self.user.pk, reservation_id=row.pk, outcome=outcome)

    def counts(self, row):
        bucket = STTPeriod.objects.get(pk=row.period_id)
        return bucket.used_ms, bucket.reserved_ms

    def parallel(self, count, function):
        barrier = Barrier(count)
        def worker(i):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return function(i)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=count) as pool:
            results = list(pool.map(worker, range(count)))
        return results

    def test_reservation_and_success_are_persistent_and_idempotent(self):
        key = uuid4()
        row = self.reserve(1001, request_id=key)
        self.assertEqual(self.counts(row), (0, 60_000))
        self.assertEqual(self.reserve(1001, request_id=key).pk, row.pk)
        self.assertTrue(self.dispatch(row))
        self.assertFalse(self.dispatch(row))
        self.settle(row, 'success')
        self.settle(row, 'success')
        self.assertEqual(self.counts(row), (60_000, 0))
        self.assertEqual(self.reserve(1001, request_id=key).state, 'consumed')
        self.assertEqual(STTReservation.objects.count(), 1)

    def test_new_connection_sees_committed_reservation(self):
        row = self.reserve()
        def read(_):
            saved = STTReservation.objects.get(pk=row.pk)
            return saved.state, saved.period.reserved_ms
        self.assertEqual(self.parallel(1, read), [('reserved', 60_000)])

    def test_pre_dispatch_failure_releases_once(self):
        row = self.reserve()
        self.settle(row, 'not_processed')
        self.settle(row, 'not_processed')
        self.assertEqual(self.counts(row), (0, 0))
        self.assertFalse(self.dispatch(row))

    def test_verified_non_processing_after_dispatch_releases(self):
        row = self.reserve()
        self.dispatch(row)
        self.settle(row, 'not_processed')
        self.assertEqual(self.counts(row), (0, 0))

    def test_uncertain_timeout_retains_hold_until_verified_result(self):
        row = self.reserve()
        self.dispatch(row)
        self.settle(row, 'uncertain')
        self.settle(row, 'uncertain')
        self.assertEqual(self.counts(row), (0, 60_000))
        self.assertFalse(self.dispatch(row))
        self.settle(row, 'success')
        self.assertEqual(self.counts(row), (60_000, 0))

    def test_uncertain_can_be_released_with_verified_non_processing(self):
        row = self.reserve()
        self.dispatch(row)
        self.settle(row, 'uncertain')
        self.settle(row, 'not_processed')
        self.assertEqual(self.counts(row), (0, 0))

    def test_crash_after_claim_does_not_allow_another_dispatch(self):
        key = uuid4()
        row = self.reserve(request_id=key)
        self.dispatch(row)
        recovered = self.reserve(request_id=key)
        self.assertEqual(recovered.state, 'dispatched')
        self.assertFalse(self.dispatch(recovered))
        self.assertEqual(self.counts(row), (0, 60_000))

    def test_success_before_dispatch_and_conflicting_settlement_rejected(self):
        row = self.reserve()
        with self.assertRaises(Conflict):
            self.settle(row, 'success')
        self.dispatch(row)
        self.settle(row, 'success')
        with self.assertRaises(Conflict):
            self.settle(row, 'not_processed')
        self.assertEqual(self.counts(row), (60_000, 0))

    def test_exact_quota_and_release_restore_capacity(self):
        row = self.reserve(7_200_000)
        with self.assertRaises(QuotaExceeded):
            self.reserve(1)
        self.settle(row, 'not_processed')
        self.reserve(7_200_000)

    def test_reused_key_with_other_duration_or_period_is_rejected(self):
        key = uuid4()
        self.reserve(request_id=key)
        with self.assertRaises(Conflict):
            self.reserve(1001, request_id=key)
        with self.assertRaises(Conflict):
            self.reserve(request_id=key, period=replace(self.period, starts_at=self.period.starts_at + timedelta(days=1)))

    def test_free_business_and_unknown_plans_are_denied(self):
        for plan in ('free', 'business', 'business_max', 'unknown'):
            with self.subTest(plan=plan), self.assertRaises(LedgerError):
                self.reserve(period=replace(self.period, plan=plan))
        self.assertEqual(STTPeriod.objects.count(), 0)

    def test_bad_periods_do_not_create_ledger_rows(self):
        now = timezone.now()
        for period in (None, replace(self.period, verification_ref=''),
                       replace(self.period, starts_at=now + timedelta(days=1)),
                       replace(self.period, ends_at=now - timedelta(seconds=1)),
                       replace(self.period, starts_at=now.replace(tzinfo=None))):
            with self.subTest(period=period), self.assertRaises(InvalidPeriod):
                self.reserve(period=period)
        self.assertEqual(STTAccount.objects.count(), 0)

    def test_invalid_duration_and_key(self):
        for duration in (0, -1, True, 1.5, 7_200_001):
            with self.subTest(duration=duration), self.assertRaises(QuotaExceeded):
                self.reserve(duration)
        with self.assertRaises(LedgerError):
            self.reserve(request_id='invalid')
        self.assertEqual(STTReservation.objects.count(), 0)

    def test_overlapping_period_and_changed_verification_fail_closed(self):
        self.reserve()
        for period in (replace(self.period, starts_at=self.period.starts_at + timedelta(days=1)),
                       replace(self.period, verification_ref='different')):
            with self.assertRaises(InvalidPeriod):
                self.reserve(period=period)
        self.assertEqual(STTPeriod.objects.count(), 1)

    def test_upgrade_and_downgrade_never_reset_usage(self):
        row = self.reserve(7_200_000)
        self.dispatch(row)
        self.settle(row, 'success')
        upgrade = self.reserve(1000, period=replace(self.period, plan='pro'))
        self.assertEqual(upgrade.period_id, row.period_id)
        with self.assertRaises(QuotaExceeded):
            self.reserve(1)
        self.assertEqual(self.counts(row), (7_200_000, 60_000))

    def test_renewal_and_late_old_settlement_do_not_mix_periods(self):
        old = self.reserve(1000)
        self.dispatch(old)
        renewed = replace(self.period, starts_at=self.period.ends_at,
                          ends_at=self.period.ends_at + timedelta(days=30), verification_ref='verified-month-2')
        with patch('ai_assistant.stt.ledger.timezone.now', return_value=renewed.starts_at):
            new = self.reserve(2000, period=renewed)
            with self.assertRaises(Conflict):
                self.reserve(1000, request_id=old.request_id, period=renewed)
            self.settle(old, 'success')
        self.assertEqual(self.counts(old), (60_000, 0))
        self.assertEqual(self.counts(new), (0, 60_000))

    def test_other_user_cannot_settle_or_dispatch(self):
        row = self.reserve()
        for function, extra in ((claim_dispatch, {}), (settle, {'outcome': 'not_processed'})):
            with self.assertRaises(LedgerError):
                function(user_id=self.other.pk, reservation_id=row.pk, **extra)
        self.assertEqual(self.counts(row), (0, 60_000))

    def test_same_request_id_is_scoped_to_account(self):
        key = uuid4()
        first = self.reserve(request_id=key)
        second = self.reserve(request_id=key, period=replace(self.period, user_id=self.other.pk))
        self.assertNotEqual(first.pk, second.pk)

    def test_failure_after_counter_update_rolls_back_everything(self):
        with patch.object(STTReservation.objects, 'create', side_effect=RuntimeError('test failure')):
            with self.assertRaises(RuntimeError):
                self.reserve()
        self.assertEqual(STTPeriod.objects.count(), 0)
        self.assertEqual(STTReservation.objects.count(), 0)

    def test_failure_during_settlement_rolls_back_counter(self):
        row = self.reserve()
        self.dispatch(row)
        with patch.object(STTReservation, 'save', side_effect=RuntimeError('test failure')):
            with self.assertRaises(RuntimeError):
                self.settle(row, 'success')
        self.assertEqual(self.counts(row), (0, 60_000))
        self.assertEqual(STTReservation.objects.get(pk=row.pk).state, 'dispatched')

    def test_dispatch_requires_commit_before_network(self):
        row = self.reserve()
        with transaction.atomic(), self.assertRaises(LedgerError):
            self.dispatch(row)
        self.assertEqual(STTReservation.objects.get(pk=row.pk).state, 'reserved')

    def test_database_constraints_enforce_invariants(self):
        row = self.reserve()
        with self.assertRaises(IntegrityError), transaction.atomic():
            STTPeriod.objects.filter(pk=row.period_id).update(reserved_ms=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            STTReservation.objects.filter(pk=row.pk).update(state='invalid')
        with self.assertRaises(IntegrityError), transaction.atomic():
            STTReservation.objects.create(account_id=row.account_id, period_id=row.period_id,
                                          request_id=row.request_id, duration_ms=1000, charge_ms=60_000)

    def test_concurrent_first_reservations_cannot_exceed_quota(self):
        def attempt(_):
            try:
                self.reserve(3_600_000)
                return 'accepted'
            except QuotaExceeded:
                return 'full'
        results = self.parallel(6, attempt)
        self.assertEqual(results.count('accepted'), 2)
        self.assertEqual(results.count('full'), 4)
        self.assertEqual(STTAccount.objects.count(), 1)
        self.assertEqual(STTPeriod.objects.get().reserved_ms, 7_200_000)

    def test_concurrent_duplicate_reservations_create_one_hold(self):
        key = uuid4()
        ids = self.parallel(6, lambda _: self.reserve(request_id=key).pk)
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(STTPeriod.objects.get().reserved_ms, 60_000)
        self.assertEqual(STTReservation.objects.count(), 1)

    def test_concurrent_dispatch_allows_one_sender(self):
        row = self.reserve()
        self.assertEqual(self.parallel(6, lambda _: self.dispatch(row)).count(True), 1)

    def test_concurrent_success_debits_once(self):
        row = self.reserve()
        self.dispatch(row)
        self.parallel(6, lambda _: self.settle(row, 'success'))
        self.assertEqual(self.counts(row), (60_000, 0))

    def test_concurrent_release_refunds_once(self):
        row = self.reserve()
        self.parallel(6, lambda _: self.settle(row, 'not_processed'))
        self.assertEqual(self.counts(row), (0, 0))

    def test_concurrent_conflicting_outcomes_cannot_double_settle(self):
        row = self.reserve()
        self.dispatch(row)
        def attempt(i):
            try:
                return self.settle(row, 'success' if i % 2 else 'not_processed').state
            except Conflict:
                return 'conflict'
        results = self.parallel(6, attempt)
        self.assertEqual(results.count('conflict'), 3)
        saved = STTReservation.objects.get(pk=row.pk)
        self.assertEqual(self.counts(row), (60_000 if saved.state == 'consumed' else 0, 0))

    def test_started_minute_boundaries_preserve_measurement_and_settle_once(self):
        total = 0
        for duration, charge in ((1, 60_000), (10_000, 60_000), (59_999, 60_000),
                                 (60_000, 60_000), (60_001, 120_000), (61_000, 120_000),
                                 (120_000, 120_000), (120_001, 180_000)):
            with self.subTest(duration=duration):
                key = uuid4()
                row = self.reserve(duration, request_id=key)
                self.assertEqual((row.duration_ms, row.charge_ms), (duration, charge))
                self.assertEqual(self.counts(row), (total, charge))
                self.assertEqual(self.reserve(duration, request_id=key).pk, row.pk)
                self.dispatch(row)
                self.settle(row, 'success')
                self.settle(row, 'success')
                total += charge
                self.assertEqual(self.counts(row), (total, 0))

    def test_rounding_is_per_request_not_total_audio(self):
        first = self.reserve(10_000)
        self.reserve(10_000)
        self.assertEqual(self.counts(first), (0, 120_000))

    def test_same_minute_different_measurement_conflicts_after_settlement(self):
        row = self.reserve(10_000)
        self.dispatch(row)
        self.settle(row, 'success')
        with self.assertRaises(Conflict):
            self.reserve(10_001, request_id=row.request_id)
        self.assertEqual(self.counts(row), (60_000, 0))

    def test_rounded_charge_enforces_remaining_quota_and_release(self):
        row = self.reserve(7_140_000)
        self.dispatch(row)
        self.settle(row, 'success')
        with self.assertRaises(QuotaExceeded):
            self.reserve(61_000)
        last = self.reserve(10_000)
        with self.assertRaises(QuotaExceeded):
            self.reserve(1)
        self.settle(last, 'not_processed')
        self.settle(last, 'not_processed')
        self.assertEqual(self.counts(row), (7_140_000, 0))
        self.reserve(60_000)
        self.assertEqual(self.counts(row), (7_140_000, 60_000))

    def test_concurrent_short_requests_compete_for_last_minute(self):
        row = self.reserve(7_140_000)
        self.dispatch(row)
        self.settle(row, 'success')
        def attempt(_):
            try:
                self.reserve(10_000)
                return True
            except QuotaExceeded:
                return False
        self.assertEqual(self.parallel(6, attempt).count(True), 1)
        self.assertEqual(self.counts(row), (7_140_000, 60_000))

    def test_two_minute_uncertain_hold_consumes_or_releases_exactly_once(self):
        for outcome in ('success', 'not_processed'):
            with self.subTest(outcome=outcome):
                row = self.reserve(61_000)
                before = self.counts(row)[0]
                self.dispatch(row)
                self.settle(row, 'uncertain')
                self.settle(row, 'uncertain')
                self.assertEqual(self.counts(row), (before, 120_000))
                self.parallel(6, lambda _: self.settle(row, outcome))
                self.assertEqual(self.counts(row), (before + (120_000 if outcome == 'success' else 0), 0))

class AudioIdentityRegressionTests(TransactionTestCase):
    setUp = LedgerTests.setUp
    reserve = LedgerTests.reserve
    counts = LedgerTests.counts

    def test_same_request_different_audio_must_conflict(self):
        key = uuid4()
        self.reserve(request_id=key, audio_sha256='a' * 64, assistant_id=101)
        with self.assertRaises(Conflict):
            self.reserve(request_id=key, audio_sha256='b' * 64, assistant_id=101)

    def test_same_request_different_assistant_must_conflict(self):
        key = uuid4()
        self.reserve(request_id=key, audio_sha256='a' * 64, assistant_id=101)
        with self.assertRaises(Conflict):
            self.reserve(request_id=key, audio_sha256='a' * 64, assistant_id=102)

    def test_legacy_reservation_without_identity_cannot_be_replayed(self):
        key = uuid4()
        row = self.reserve(request_id=key)
        STTReservation.objects.filter(pk=row.pk).update(
            audio_sha256=None, assistant_id=None)

        with self.assertRaises(Conflict):
            self.reserve(request_id=key)

        self.assertEqual(STTReservation.objects.count(), 1)
        self.assertEqual(self.counts(row), (0, 60_000))

    def test_same_audio_and_assistant_is_idempotent(self):
        key = uuid4()
        first = self.reserve(request_id=key, audio_sha256='a' * 64, assistant_id=101)
        second = self.reserve(request_id=key, audio_sha256='a' * 64, assistant_id=101)
        self.assertEqual(first.pk, second.pk)
