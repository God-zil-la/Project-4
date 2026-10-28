"""U6.3 database integration tests using the existing U6.1 ledger."""

from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

from ai_assistant.stt import ledger
from ai_assistant.stt.models import STTPeriod, STTReservation
from ai_assistant.stt.normalizer import (
    ServerPeriodEvidence,
    claim_normalized,
    reserve_normalized,
)


class VoiceSTTLedgerIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="voice-stt-integration-owner"
        )
        now = timezone.now()
        self.evidence = ServerPeriodEvidence(
            self.user.pk,
            "stripe",
            "sandbox",
            "voice-integration-subscription",
            "voice-integration-cycle",
            "premium",
            now - timedelta(days=15),
            now + timedelta(days=15),
            now,
            True,
            True,
            "ordinary_monthly",
        )

    def test_real_reservation_dispatch_and_settlement(self):
        reservation = reserve_normalized(
            evidence=self.evidence,
            request_id=uuid4(),
            duration_ms=61000,
            audio_sha256="a" * 64,
            assistant_id=101,
        )

        self.assertEqual(reservation.state, "reserved")
        self.assertEqual(reservation.charge_ms, 120000)

        period = STTPeriod.objects.get(pk=reservation.period_id)
        self.assertEqual(period.reserved_ms, 120000)
        self.assertEqual(period.used_ms, 0)

        claimed = claim_normalized(
            evidence=self.evidence,
            reservation_id=reservation.pk,
        )
        self.assertTrue(claimed)

        reservation.refresh_from_db()
        self.assertEqual(reservation.state, "dispatched")

        ledger.settle(
            user_id=self.user.pk,
            reservation_id=reservation.pk,
            outcome="success",
        )

        reservation.refresh_from_db()
        period.refresh_from_db()

        self.assertEqual(reservation.state, "consumed")
        self.assertEqual(period.reserved_ms, 0)
        self.assertEqual(period.used_ms, 120000)

        ledger.settle(
            user_id=self.user.pk,
            reservation_id=reservation.pk,
            outcome="success",
        )

        period.refresh_from_db()
        self.assertEqual(period.reserved_ms, 0)
        self.assertEqual(period.used_ms, 120000)

    def test_pipeline_dispatch_transaction_boundary(self):
        """Real ledger dispatch through U6.3 must respect transaction rules."""
        from unittest.mock import Mock, patch
        from types import SimpleNamespace

        from ai_assistant.voice.stt_pipeline import execute_testable_stt

        request_id = uuid4()
        audio_hash = "b" * 64

        reservation = reserve_normalized(
            evidence=self.evidence,
            request_id=request_id,
            duration_ms=1000,
            audio_sha256=audio_hash,
            assistant_id=101,
        )

        session = SimpleNamespace(
            public_id=uuid4(),
            assistant_id=101,
        )
        turn = SimpleNamespace(
            request_id=request_id,
            audio_sha256=audio_hash,
        )
        audio = SimpleNamespace(sha256=audio_hash)
        transcriber = Mock(return_value="Integration test transcript")

        with (
            patch("ai_assistant.voice.service._session"),
            patch(
                "ai_assistant.voice.stt_pipeline.prepare_reserved_stt",
                return_value=(session, turn),
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.advance_turn",
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.accept_stt_result",
            ),
        ):
            execute_testable_stt(
                user=self.user,
                session_id=session.public_id,
                request_id=request_id,
                reservation=reservation,
                evidence=self.evidence,
                audio=audio,
                transcriber=transcriber,
            )

        reservation.refresh_from_db()
        self.assertEqual(reservation.state, "consumed")
        transcriber.assert_called_once_with(audio)
