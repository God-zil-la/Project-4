from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase

from .live_session_timer import (
    LiveSessionTimerError,
    finalized_charge,
    timer_snapshot,
)


UTC = dt_timezone.utc


class LiveSessionTimerTests(SimpleTestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

    def test_active_time_includes_silence(self):
        snapshot = timer_snapshot(
            started_at=self.start,
            reserved_ms=600000,
            observed_at=self.start + timedelta(seconds=75),
        )
        self.assertEqual(snapshot.chargeable_ms, 75000)
        self.assertEqual(snapshot.remaining_ms, 525000)

    def test_exact_deadline(self):
        snapshot = timer_snapshot(
            started_at=self.start,
            reserved_ms=600000,
            observed_at=self.start + timedelta(minutes=10),
        )
        self.assertTrue(snapshot.expired)
        self.assertEqual(snapshot.chargeable_ms, 600000)
        self.assertEqual(snapshot.remaining_ms, 0)

    def test_late_stop_cannot_exceed_reservation(self):
        charge = finalized_charge(
            started_at=self.start,
            reserved_ms=600000,
            ended_at=self.start + timedelta(hours=3),
        )
        self.assertEqual(charge, 600000)

    def test_early_stop_charges_only_elapsed_time(self):
        charge = finalized_charge(
            started_at=self.start,
            reserved_ms=600000,
            ended_at=self.start + timedelta(seconds=22),
        )
        self.assertEqual(charge, 22000)

    def test_month_boundary_caps_charge(self):
        start = datetime(2026, 10, 31, 23, 59, 30, tzinfo=UTC)
        period_end = datetime(2026, 11, 1, tzinfo=UTC)

        snapshot = timer_snapshot(
            started_at=start,
            reserved_ms=600000,
            observed_at=start + timedelta(minutes=2),
            monthly_period_end=period_end,
        )
        self.assertEqual(snapshot.chargeable_ms, 30000)
        self.assertTrue(snapshot.expired)

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(LiveSessionTimerError):
            timer_snapshot(
                started_at=datetime(2026, 10, 24),
                reserved_ms=600000,
                observed_at=self.start,
            )

    def test_invalid_reservation_rejected(self):
        for duration in (-1, 0, True, 600001):
            with self.subTest(duration=duration):
                with self.assertRaises(LiveSessionTimerError):
                    timer_snapshot(
                        started_at=self.start,
                        reserved_ms=duration,
                        observed_at=self.start,
                    )

    def test_clock_regression_rejected(self):
        with self.assertRaises(LiveSessionTimerError):
            timer_snapshot(
                started_at=self.start,
                reserved_ms=600000,
                observed_at=self.start - timedelta(seconds=1),
            )

    def test_same_server_timestamps_are_idempotent(self):
        kwargs = {
            "started_at": self.start,
            "reserved_ms": 600000,
            "ended_at": self.start + timedelta(seconds=42),
        }
        self.assertEqual(
            finalized_charge(**kwargs),
            finalized_charge(**kwargs),
        )