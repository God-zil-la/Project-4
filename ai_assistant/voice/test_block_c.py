from datetime import datetime, timedelta, timezone as utc
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase
from django.contrib.auth import get_user_model
from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceSession
from .live_quota_models import LiveVoiceMonthlyUsage
from .live_quota_policy import free_monthly_period
from .service import start_session, stop_session, reserve_turn, _session, VoiceConflict, VoiceAccessDenied, reconcile_expired_sessions

class BlockCTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="block_c")
        self.bot = Bot.objects.create(owner=self.user, name="Block C")
        self.conversation = Conversation.objects.create(user=self.user, bot=self.bot)
        self.now = datetime(2026, 10, 24, 12, tzinfo=utc.utc)
    def start(self):
        return start_session(user=self.user, assistant=self.bot, conversation=self.conversation)
    def test_remaining_and_idempotent_stop(self):
        start, end = free_monthly_period(self.now)
        usage = LiveVoiceMonthlyUsage.objects.create(user=self.user, period_start=start, period_end=end, used_ms=599000)
        with patch("django.utils.timezone.now", return_value=self.now):
            session = self.start()
            self.assertEqual(session.quota_reservation.duration_ms, 1000)
            with self.assertRaises(VoiceConflict): self.start()
        with patch("django.utils.timezone.now", return_value=self.now+timedelta(milliseconds=250)):
            stop_session(user=self.user, session_id=session.public_id)
        with patch("django.utils.timezone.now", return_value=self.now+timedelta(seconds=10)):
            stop_session(user=self.user, session_id=session.public_id)
        usage.refresh_from_db()
        self.assertEqual((usage.used_ms, usage.reserved_ms), (599250, 0))
    def test_expiry_blocks_turn_and_reconciles_once(self):
        with patch("django.utils.timezone.now", return_value=self.now): session=self.start()
        with patch("django.utils.timezone.now", return_value=session.deadline_at):
            with self.assertRaises(VoiceAccessDenied):
                reserve_turn(user=self.user, session_id=session.public_id, request_id=uuid4(), audio_sha256="a"*64)
            reconcile_expired_sessions(user=self.user)
            reconcile_expired_sessions(user=self.user)
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(600000,0))
    def test_month_boundary(self):
        self.now=datetime(2026,10,31,23,59,59,tzinfo=utc.utc)
        with patch("django.utils.timezone.now",return_value=self.now): session=self.start()
        self.assertEqual(session.deadline_at, datetime(2026,11,1,tzinfo=utc.utc))
        with patch("django.utils.timezone.now",return_value=self.now+timedelta(days=1)):
            reconcile_expired_sessions(user=self.user)
            fresh=self.start()
        old=session.quota_reservation.usage
        old.refresh_from_db()
        self.assertEqual((old.used_ms,old.reserved_ms),(1000,0))
        self.assertNotEqual(fresh.quota_reservation.usage_id,old.pk)
    def test_start_rolls_back_reservation(self):
        with patch("django.utils.timezone.now", return_value=self.now), patch.object(VoiceSession.objects,"create",side_effect=RuntimeError):
            with self.assertRaises(RuntimeError): self.start()
        self.assertFalse(LiveVoiceMonthlyUsage.objects.filter(user=self.user).exists())

    def test_expired_session_never_dispatches_ai_or_tts(self):
        from .ai_adapter import process_voice_answer
        from .tts_adapter import synthesize_voice_answer
        from .service import claim_ai_dispatch, claim_tts_dispatch
        with patch("django.utils.timezone.now", return_value=self.now): session=self.start()
        args=dict(user=self.user,session_id=session.public_id,request_id=uuid4())
        with patch("django.utils.timezone.now",return_value=session.deadline_at), patch("ai_assistant.voice.ai_adapter.process_bot_message") as ai, patch("ai_assistant.voice.tts_adapter.synthesize_saved_response") as tts:
            for action in [process_voice_answer,synthesize_voice_answer,claim_ai_dispatch,claim_tts_dispatch]:
                with self.assertRaises(VoiceAccessDenied): action(**args)
            ai.assert_not_called()
            tts.assert_not_called()
