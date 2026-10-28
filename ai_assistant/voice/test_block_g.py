"""Block G audit: owner/plan boundaries, explicit mocks, cleanup and real races."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import OperationalError, close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from ai_assistant.accounts.models import UserProfile
from ai_assistant.bots.models import Bot, Conversation
from ai_assistant.tts.authorization import authorize
from ai_assistant.tts.errors import AuthorizationDenied
from . import test_block_e as fixtures
from .free_voice_chain import VoiceChainProviders, voice_chain_providers
from .live_quota_models import LiveVoiceMonthlyUsage
from .live_quota_service import commit_free_voice, LiveVoiceQuotaConflict
from .models import VoiceSession, VoiceTurn
from .server_dependencies import resolve_local_http_voice_dependencies
from .local_live_voice import build_local_live_voice_dependencies
from .service import start_session, stop_session, reconcile_expired_sessions, reserve_turn, VoiceAccessDenied, VoiceConflict


@override_settings(DEBUG=True,U63_VOICE_TEST_DOUBLES=True)
class BlockGChainAuditTests(TestCase):
    setUp=fixtures.BlockEChainTests.setUp
    local_mock_ai=fixtures.BlockEChainTests.local_mock_ai
    response=staticmethod(fixtures.BlockEChainTests.response)
    upload=fixtures.BlockEChainTests.upload
    turn_url=fixtures.BlockEChainTests.turn_url

    def test_missing_mock_ai_cannot_fall_back_to_the_live_engine(self):
        with voice_chain_providers(VoiceChainProviders(self.transcribe,self.synthesize)):
            self.assertEqual(self.upload().status_code,503)
        self.completion.assert_not_called();self.transcribe.assert_not_called()
        self.assertFalse(VoiceTurn.objects.exists())

    def test_explicit_mock_ai_never_invokes_original_openai_dispatch(self):
        local=Mock(return_value=self.response("A fully local answer."))
        self.completion.side_effect=AssertionError("Original OpenAI dispatch must not run in mock mode")
        with voice_chain_providers(VoiceChainProviders(self.transcribe,self.synthesize,mock_ai=local)):
            self.assertEqual(self.upload().json()["result"]["state"],"completed")
        local.assert_called_once();self.completion.assert_not_called()
        self.assertIn("A fully local answer",VoiceTurn.objects.get().assistant_message.message)

    def test_failing_mock_never_falls_back_or_retries_ai(self):
        local=Mock(side_effect=RuntimeError("Incomplete local test response"))
        with voice_chain_providers(VoiceChainProviders(self.transcribe,self.synthesize,mock_ai=local)):
            self.assertEqual(self.upload().json()["result"]["state"],"uncertain")
            self.assertEqual(self.upload().json()["result"]["state"],"uncertain")
        local.assert_called_once();self.completion.assert_not_called();self.synthesize.assert_not_called()

    def test_slow_stage_authorization_cannot_start_stt_after_deadline(self):
        def delayed(**kwargs):
            if VoiceTurn.objects.filter(state=VoiceTurn.State.TRANSCRIBING).exists():
                self.clock=self.session.deadline_at
            return self.user.profile
        with patch("ai_assistant.voice.free_voice_chain.require_free_voice_access",side_effect=delayed):
            self.assertEqual(self.upload().status_code,409)
        self.transcribe.assert_not_called();self.completion.assert_not_called()

    def test_deactivated_account_can_be_settled_but_cannot_start_new_work(self):
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        # Even a stale in-memory principal cannot reserve a new voice turn.
        with self.assertRaises(VoiceAccessDenied):
            reserve_turn(user=self.user,session_id=self.session.public_id,request_id=uuid4(),audio_sha256="a"*64)
        self.user.refresh_from_db();self.clock=self.session.deadline_at+timedelta(seconds=2)
        reconcile_expired_sessions(user=self.user);reconcile_expired_sessions(user=self.user)
        self.session.refresh_from_db()
        self.assertFalse(self.session.active);self.assertEqual(self.session.ended_at,self.session.deadline_at)
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(600000,0))
        self.completion.assert_not_called()

    def test_public_quota_commit_still_refuses_inactive_principal(self):
        self.user.is_active=False
        with self.assertRaises(LiveVoiceQuotaConflict):
            commit_free_voice(user=self.user,request_id=self.session.quota_reservation.request_id,consumed_ms=0)

    def test_cross_owner_audio_replay_cannot_access_local_output(self):
        self.upload();self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.turn_url()+"audio/").status_code,404)
        self.assertEqual(self.client.get(self.turn_url()).status_code,404)
        self.assertEqual(self.client.post(f"/api/live-voice/{self.session.public_id}/stop/").status_code,404)

    def test_legacy_environment_flags_do_not_grant_provider_approval(self):
        with patch.dict(os.environ,{"U63_LOCAL_LIVE_VOICE_ENABLED":"true","U63_REAL_STT_ENABLED":"true","U63_REAL_TTS_ENABLED":"true"}),override_settings(U63_EXTERNAL_PROVIDER_APPROVAL=False),patch("ai_assistant.voice.local_live_voice.build_local_live_voice_dependencies") as build:
            request=Mock(user=self.user)
            self.assertIsNone(resolve_local_http_voice_dependencies(request=request))
            build.assert_not_called()

    def test_direct_local_builder_requires_explicit_approval_and_argument(self):
        with override_settings(U63_EXTERNAL_PROVIDER_APPROVAL=False):
            with self.assertRaisesRegex(RuntimeError,"approval_required"):
                build_local_live_voice_dependencies(user=self.user,allow_paid_calls=True)
        with override_settings(U63_EXTERNAL_PROVIDER_APPROVAL=True):
            with self.assertRaisesRegex(RuntimeError,"approval_required"):
                build_local_live_voice_dependencies(user=self.user)


class BlockGEntitlementAuditTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username="g-entitlement")
        self.bot=Bot.objects.create(owner=self.user,name="Audit")
        self.conversation=Conversation.objects.create(user=self.user,bot=self.bot)
        self.client.force_login(self.user)

    def start(self):
        return self.client.post("/api/live-voice/start/",{"assistant_id":self.bot.pk,
            "conversation_id":str(self.conversation.public_id),"request_id":str(uuid4())},content_type="application/json")

    def test_premium_pro_unknown_and_active_k1_do_not_consume_free_quota(self):
        for plan in ['premium','pro','unknown']:
            with self.subTest(plan=plan):
                UserProfile.objects.filter(user=self.user).update(plan=plan)
                self.assertEqual(self.start().status_code,403)
        UserProfile.objects.filter(user=self.user).update(plan='free',campaign_started_at=timezone.now(),campaign_ends_at=timezone.now()+timedelta(days=2))
        self.assertEqual(self.start().status_code,403)
        self.assertFalse(LiveVoiceMonthlyUsage.objects.exists())

    def test_expired_k1_reverts_to_free_without_reusing_k1_allowance(self):
        UserProfile.objects.filter(user=self.user).update(plan='free',campaign_started_at=timezone.now()-timedelta(days=20),campaign_ends_at=timezone.now()-timedelta(days=1))
        self.assertEqual(self.start().status_code,201)
        self.assertEqual(LiveVoiceMonthlyUsage.objects.get(user=self.user).reserved_ms,600000)

    def test_u62_effective_entitlements_remain_unchanged(self):
        for plan in ['premium','pro']:
            with self.subTest(plan=plan):
                UserProfile.objects.filter(user=self.user).update(plan=plan)
                self.assertEqual(authorize(self.user,self.bot.pk),self.user.pk)
        UserProfile.objects.filter(user=self.user).update(plan='free',campaign_started_at=timezone.now(),campaign_ends_at=timezone.now()+timedelta(days=2))
        self.assertEqual(authorize(self.user,self.bot.pk),self.user.pk) # existing K1 effective Pro policy
        UserProfile.objects.filter(user=self.user).update(campaign_ends_at=timezone.now()-timedelta(days=1))
        with self.assertRaises(AuthorizationDenied):authorize(self.user,self.bot.pk)

    def test_malformed_conversation_uuid_returns_controlled_error(self):
        response=self.client.post("/api/live-voice/start/",{"assistant_id":self.bot.pk,"conversation_id":"not-a-uuid"},content_type="application/json")
        self.assertEqual(response.status_code,400)
        self.assertFalse(VoiceSession.objects.exists())

    def test_session_auth_requires_csrf_for_mutating_voice_api(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        response=client.post("/api/live-voice/start/",{"assistant_id":self.bot.pk,"conversation_id":str(self.conversation.public_id)},content_type="application/json")
        self.assertEqual(response.status_code,403)
        self.assertFalse(VoiceSession.objects.exists())

    def test_anonymous_start_has_no_quota_side_effect(self):
        self.client.logout();self.assertEqual(self.start().status_code,401)
        self.assertFalse(LiveVoiceMonthlyUsage.objects.exists())


class BlockGConcurrentAuditTests(TransactionTestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username="g-race")
        self.bot=Bot.objects.create(owner=self.user,name="Race")
        self.conversation=Conversation.objects.create(user=self.user,bot=self.bot)

    def worker(self,barrier,request_id):
        close_old_connections()
        try:
            user=get_user_model().objects.get(pk=self.user.pk)
            bot=Bot.objects.get(pk=self.bot.pk);conversation=Conversation.objects.get(pk=self.conversation.pk)
            barrier.wait(timeout=10)
            try:
                return ('ok',start_session(user=user,assistant=bot,conversation=conversation,request_id=request_id).pk)
            except (OperationalError,VoiceConflict):return ('blocked',None)
        finally:connections.close_all()

    def test_real_sqlite_parallel_starts_cannot_overreserve(self):
        barrier=Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda key:self.worker(barrier,key),[uuid4(),uuid4()]))
        self.assertLessEqual(VoiceSession.objects.count(),1)
        usage=LiveVoiceMonthlyUsage.objects.filter(user=self.user).first()
        if usage:self.assertLessEqual(usage.used_ms+usage.reserved_ms,600000)
        # A lock loser may retry only after rolling back its transaction.
        if not VoiceSession.objects.exists():
            start_session(user=self.user,assistant=self.bot,conversation=self.conversation,request_id=uuid4())
        self.assertEqual(VoiceSession.objects.count(),1)

    def test_real_sqlite_parallel_retry_retains_one_start_identity(self):
        identity=uuid4();barrier=Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda key:self.worker(barrier,key),[identity,identity]))
        recovered=start_session(user=self.user,assistant=self.bot,conversation=self.conversation,request_id=identity)
        self.assertEqual(VoiceSession.objects.count(),1)
        self.assertEqual(VoiceSession.objects.get().pk,recovered.pk)
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(0,600000))
