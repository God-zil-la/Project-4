from dataclasses import replace
from datetime import timedelta, timezone as dt_timezone
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.db import connection
from unittest import skipIf
from django.utils import timezone

from . import ledger, test_ledger as helpers
from .models import STTPeriod, STTPeriodBinding, STTReservation
from .normalizer import ServerPeriodEvidence, normalize, reserve_normalized, claim_normalized


class NormalizerTests(TransactionTestCase):
    parallel = helpers.LedgerTests.parallel

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='normalized-owner')
        self.now = timezone.now()
        self.evidence = ServerPeriodEvidence(
            self.user.pk, 'stripe', 'sandbox', 'subscription-1', 'cycle-1', 'premium',
            self.now - timedelta(days=15), self.now + timedelta(days=15), self.now,
            True, True, 'ordinary_monthly')

    def reserve(self, evidence=None, key=None, duration=1000):
        return reserve_normalized(evidence=evidence or self.evidence,
                                  request_id=key or uuid4(), duration_ms=duration,
                                  audio_sha256='a' * 64, assistant_id=101)

    def settle(self, row, outcome):
        return ledger.settle(user_id=self.user.pk, reservation_id=row.pk, outcome=outcome)

    def test_supported_sources_and_utc_output(self):
        for source in ('stripe', 'apple', 'google'):
            period = normalize(replace(self.evidence, provider=source))
            self.assertEqual(period.starts_at.tzinfo, dt_timezone.utc)
            self.assertEqual(period.ends_at, self.evidence.ends_at)

    def test_metadata_and_reverification_do_not_change_identity_or_usage(self):
        key = uuid4()
        row = self.reserve(key=key)
        changed = replace(self.evidence, verified_at=timezone.now(), metadata={'event': 'new', 'label': 'changed'})
        self.assertEqual(normalize(changed).verification_ref, normalize(self.evidence).verification_ref)
        self.assertEqual(self.reserve(changed, key).pk, row.pk)
        self.assertEqual(STTPeriod.objects.count(), 1)
        self.assertEqual(STTPeriod.objects.get().reserved_ms, 60_000)

    def test_missing_unverified_and_contradictory_evidence(self):
        variants = [None, {}, replace(self.evidence, verification_succeeded=False),
                    replace(self.evidence, entitlement_active=False),
                    replace(self.evidence, cycle_id=''), replace(self.evidence, subscription_id=' '),
                    replace(self.evidence, user_id=True), replace(self.evidence, ends_at=self.evidence.starts_at),
                    replace(self.evidence, verified_at=self.now + timedelta(days=1)),
                    replace(self.evidence, verified_at=self.evidence.starts_at - timedelta(seconds=1))]
        for evidence in variants:
            with self.subTest(evidence=evidence), self.assertRaises(ledger.InvalidPeriod):
                normalize(evidence)

    def test_naive_and_non_utc_dates_are_rejected(self):
        for field in ('starts_at', 'ends_at', 'verified_at'):
            for value in (getattr(self.evidence, field).replace(tzinfo=None),
                          getattr(self.evidence, field).astimezone(dt_timezone(timedelta(hours=2)))):
                with self.subTest(field=field), self.assertRaises(ledger.InvalidPeriod):
                    normalize(replace(self.evidence, **{field: value}))

    def test_open_policy_categories_are_not_guessed(self):
        for category in ('campaign', 'trial', 'administrative', 'upgrade', 'downgrade', 'grace', ''):
            with self.subTest(category=category), self.assertRaises(ledger.InvalidPeriod):
                self.reserve(replace(self.evidence, category=category))
        with self.assertRaises(ledger.InvalidPeriod):
            self.reserve(replace(self.evidence, provider='admin'))
        self.assertEqual(STTPeriod.objects.count(), 0)

    def test_start_inclusive_end_exclusive(self):
        start, end = self.evidence.starts_at, self.evidence.ends_at
        for moment, accepted in ((start - timedelta(microseconds=1), False), (start, True),
                                  (end - timedelta(microseconds=1), True), (end, False)):
            with self.subTest(moment=moment), patch('django.utils.timezone.now', return_value=moment):
                evidence = replace(self.evidence, verified_at=start)
                if accepted:
                    normalize(evidence)
                else:
                    with self.assertRaises(ledger.InvalidPeriod):
                        normalize(evidence)

    def test_cycle_cannot_be_reused_for_nonoverlapping_new_dates(self):
        self.reserve()
        future = replace(self.evidence, starts_at=self.evidence.ends_at,
                         ends_at=self.evidence.ends_at + timedelta(days=30), verified_at=self.evidence.ends_at)
        with patch('django.utils.timezone.now', return_value=future.starts_at):
            with self.assertRaises(ledger.InvalidPeriod):
                self.reserve(future)
        self.assertEqual(STTPeriod.objects.count(), 1)

    def test_different_identity_cannot_create_overlapping_bucket(self):
        self.reserve()
        for changes in ({'cycle_id': 'other'}, {'provider': 'apple'},
                        {'cycle_id': 'other', 'starts_at': self.evidence.starts_at + timedelta(days=1)}):
            with self.assertRaises(ledger.InvalidPeriod):
                self.reserve(replace(self.evidence, **changes))
        self.assertEqual(STTPeriod.objects.count(), 1)

    def test_plan_change_in_existing_period_is_blocked(self):
        self.reserve()
        with self.assertRaises(ledger.InvalidPeriod):
            self.reserve(replace(self.evidence, plan='pro'))
        self.assertEqual(STTPeriod.objects.get().reserved_ms, 60_000)

    def test_period_expires_during_reservation_lock_wait(self):
        clock = [self.now]
        original = ledger._lock_account
        def lock(user_id):
            result = original(user_id)
            clock[0] = self.evidence.ends_at
            return result
        with patch('django.utils.timezone.now', side_effect=lambda: clock[0]), patch.object(ledger, '_lock_account', side_effect=lock):
            with self.assertRaises(ledger.InvalidPeriod):
                self.reserve()
        self.assertEqual(STTPeriod.objects.count(), 0)
        self.assertEqual(STTPeriodBinding.objects.count(), 0)

    def test_delayed_dispatch_at_end_is_rejected_without_refund(self):
        row = self.reserve()
        with patch('django.utils.timezone.now', return_value=self.evidence.ends_at):
            with self.assertRaises(ledger.InvalidPeriod):
                claim_normalized(evidence=self.evidence, reservation_id=row.pk)
            with self.assertRaises(ledger.InvalidPeriod):
                ledger.claim_dispatch(user_id=self.user.pk, reservation_id=row.pk)
        row.refresh_from_db()
        self.assertEqual(row.state, 'reserved')
        self.assertEqual(row.period.reserved_ms, 60_000)

    def test_period_expires_during_dispatch_lock_wait(self):
        row = self.reserve()
        clock = [self.now]
        original = ledger._lock_account
        def lock(user_id):
            result = original(user_id)
            clock[0] = self.evidence.ends_at
            return result
        with patch('django.utils.timezone.now', side_effect=lambda: clock[0]), patch.object(ledger, '_lock_account', side_effect=lock):
            with self.assertRaises(ledger.InvalidPeriod):
                claim_normalized(evidence=self.evidence, reservation_id=row.pk)
        row.refresh_from_db()
        self.assertEqual(row.state, 'reserved')

    def test_old_reservation_cannot_be_dispatched_with_new_period(self):
        row = self.reserve()
        future = replace(self.evidence, cycle_id='cycle-2', starts_at=self.evidence.ends_at,
                         ends_at=self.evidence.ends_at + timedelta(days=30), verified_at=self.evidence.ends_at)
        with patch('django.utils.timezone.now', return_value=future.starts_at):
            self.reserve(future)
            with self.assertRaises(ledger.InvalidPeriod):
                claim_normalized(evidence=future, reservation_id=row.pk)

    def test_uncertain_old_outcome_stays_in_original_bucket(self):
        row = self.reserve()
        self.assertTrue(claim_normalized(evidence=self.evidence, reservation_id=row.pk))
        self.settle(row, 'uncertain')
        future = replace(self.evidence, cycle_id='cycle-2', starts_at=self.evidence.ends_at,
                         ends_at=self.evidence.ends_at + timedelta(days=30), verified_at=self.evidence.ends_at)
        with patch('django.utils.timezone.now', return_value=future.starts_at):
            new = self.reserve(future)
            self.settle(row, 'success')
            self.settle(row, 'success')
        row.period.refresh_from_db()
        new.period.refresh_from_db()
        self.assertEqual((row.period.used_ms, row.period.reserved_ms), (60_000, 0))
        self.assertEqual((new.period.used_ms, new.period.reserved_ms), (0, 60_000))

    @skipIf(connection.vendor == 'sqlite', 'Concurrent writes verified on PostgreSQL')
    def test_concurrent_metadata_variants_share_one_reservation(self):
        key = uuid4()
        ids = self.parallel(6, lambda i: self.reserve(replace(self.evidence, metadata={'event': i}), key).pk)
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(STTPeriodBinding.objects.count(), 1)
        self.assertEqual(STTPeriod.objects.get().reserved_ms, 60_000)

    @skipIf(connection.vendor == 'sqlite', 'Concurrent writes verified on PostgreSQL')
    def test_concurrent_conflicting_periods_allow_only_one(self):
        def attempt(i):
            try:
                self.reserve(replace(self.evidence, starts_at=self.evidence.starts_at + timedelta(seconds=i)))
                return True
            except ledger.InvalidPeriod:
                return False
        self.assertEqual(self.parallel(6, attempt).count(True), 1)
        self.assertEqual(STTPeriod.objects.count(), 1)
        self.assertEqual(STTPeriodBinding.objects.count(), 1)

    def test_concurrent_release_and_dispatch_have_safe_outcomes(self):
        row = self.reserve()
        @ledger._atomic_operation
        def cancel_before_dispatch():
            locked = ledger._locked_reservation(self.user.pk, row.pk)
            if locked.state == 'reserved':
                self.settle(locked, 'not_processed')
        def attempt(i):
            if i % 2:
                return claim_normalized(evidence=self.evidence, reservation_id=row.pk)
            # A pre-dispatch cancellation must not refund an already sent request.
            cancel_before_dispatch()
            return False
        results = self.parallel(6, attempt)
        self.assertLessEqual(results.count(True), 1)
        saved = STTReservation.objects.get(pk=row.pk)
        self.assertIn(saved.state, ('released', 'dispatched'))
        self.assertEqual(saved.period.used_ms, 0)
        self.assertEqual(saved.period.reserved_ms, 0 if saved.state == 'released' else 60_000)
