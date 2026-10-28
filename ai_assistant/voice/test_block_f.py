"""Block F: immediate provider-boundary checks; no external network/cost."""
from contextvars import Context
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase, override_settings
from ai_assistant.bots import chat_service, knowledge_utils, document_ai_intent, document_workbook
from ai_assistant.bots.models import ChatMessage
from . import test_block_e as fixtures
from . import provider_boundary
from .provider_guard import voice_provider_scope, has_voice_scope
from .models import VoiceSession, VoiceTurn
from .service import VoiceAccessDenied
from .live_quota_models import LiveVoiceMonthlyUsage


@override_settings(DEBUG=True, U63_VOICE_TEST_DOUBLES=True)
class BlockFProviderTests(TestCase):
    setUp = fixtures.BlockEChainTests.setUp
    local_mock_ai = fixtures.BlockEChainTests.local_mock_ai
    response = staticmethod(fixtures.BlockEChainTests.response)
    upload = fixtures.BlockEChainTests.upload
    turn_url = fixtures.BlockEChainTests.turn_url

    def processing(self):
        return VoiceTurn.objects.create(session=self.session,request_id=self.request_id,
            audio_sha256="a"*64,state=VoiceTurn.State.PROCESSING,transcript="Voice request")

    def scope(self):
        return voice_provider_scope(user=self.user,session_id=self.session.public_id,request_id=self.request_id)

    def test_valid_voice_provider_is_called_once(self):
        self.processing();create=Mock(return_value={"ok":True})
        with self.scope():
            self.assertEqual(provider_boundary.provider_call(create,model="local-test"),{"ok":True})
        create.assert_called_once_with(model="local-test")
        self.assertFalse(has_voice_scope())

    def test_exact_deadline_blocks_before_any_billing_or_provider_call(self):
        self.processing();self.clock=self.session.deadline_at;create=Mock()
        with self.scope(),patch.object(provider_boundary,"_campaign_provider_call") as billing:
            with self.assertRaises(VoiceAccessDenied): provider_boundary.provider_call(create)
        billing.assert_not_called();create.assert_not_called()
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(0,600000))

    def test_expiry_during_pre_dispatch_work_is_rechecked_at_actual_call(self):
        self.processing();create=Mock()
        def delayed_billing(guarded,**kwargs):
            self.clock=self.session.deadline_at
            return guarded(model="local-test")
        with self.scope(),patch.object(provider_boundary,"_campaign_provider_call",side_effect=delayed_billing):
            with self.assertRaises(VoiceAccessDenied): provider_boundary.provider_call(create)
        create.assert_not_called()

    def test_stop_immediately_before_provider_prevents_dispatch(self):
        self.processing();create=Mock()
        self.client.post(f"/api/live-voice/{self.session.public_id}/stop/")
        with self.scope():
            with self.assertRaises(VoiceAccessDenied): provider_boundary.provider_call(create)
        create.assert_not_called()

    def test_account_revocation_between_checks_prevents_dispatch(self):
        self.processing();create=Mock()
        def delayed(guarded,**kwargs):
            type(self.user).objects.filter(pk=self.user.pk).update(is_active=False)
            return guarded()
        with self.scope(),patch.object(provider_boundary,"_campaign_provider_call",side_effect=delayed):
            with self.assertRaises(VoiceAccessDenied): provider_boundary.provider_call(create)
        create.assert_not_called()

    def test_other_turn_identity_cannot_borrow_the_session(self):
        self.processing();create=Mock()
        with voice_provider_scope(user=self.user,session_id=self.session.public_id,request_id=uuid4()):
            with self.assertRaises(VoiceAccessDenied): provider_boundary.provider_call(create)
        create.assert_not_called()

    def test_scope_isolated_from_other_context_and_restored_after_exception(self):
        self.processing()
        with self.assertRaises(RuntimeError):
            with self.scope():
                self.assertTrue(has_voice_scope())
                self.assertFalse(Context().run(has_voice_scope))
                raise RuntimeError("Local simulated failure")
        self.assertFalse(has_voice_scope())

    def test_text_chat_remains_allowed_when_voice_deadline_has_expired(self):
        self.clock=self.session.deadline_at
        with patch.object(provider_boundary,"check_provider_allowed",side_effect=AssertionError("Text chat must not use voice guard")):
            result=chat_service.process_bot_message(user=self.user,bot=self.bot,
                message="What are the opening hours?",conversation=self.conversation.public_id)
        self.assertIn("open at nine",result["response"])
        self.completion.assert_called_once()
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),4)

    def test_nonvoice_billing_receives_the_original_callable_and_arguments(self):
        create=Mock();sentinel=object()
        with patch.object(provider_boundary,"_campaign_provider_call",return_value=sentinel) as billing:
            result=provider_boundary.provider_call(create,campaign_user=self.user,model="local-test",max_tokens=4)
        self.assertIs(result,sentinel)
        billing.assert_called_once_with(create,campaign_user=self.user,model="local-test",max_tokens=4)
        create.assert_not_called()

    def test_all_reachable_ai_helper_boundaries_reject_expired_voice(self):
        self.processing();self.clock=self.session.deadline_at
        with self.scope():
            for module in [chat_service,knowledge_utils,document_ai_intent,document_workbook]:
                with self.subTest(module=module.__name__):
                    create=Mock()
                    with self.assertRaises(VoiceAccessDenied): module.provider_call(create,model="local-test")
                    create.assert_not_called()

    def test_actual_embedding_batch_loop_stops_after_deadline(self):
        self.processing()
        def embedding(**kwargs):
            self.clock=self.session.deadline_at
            return {"data":[{"index":0,"embedding":[1.0,0.0]}],"usage":{"prompt_tokens":1,"total_tokens":1}}
        with self.scope(),patch("openai.Embedding.create",side_effect=embedding) as create:
            with self.assertRaises(VoiceAccessDenied):
                knowledge_utils.generate_embedding_batches(["First chunk","Second chunk"],Mock(),batch_size=1)
        self.assertEqual(create.call_count,1)

    def test_slow_kb_retrieval_cannot_start_final_answer_after_deadline(self):
        def retrieval(*args,**kwargs):
            self.clock=self.session.deadline_at
            return {"chunks":[],"sources":[],"tokens_used":0,"input_tokens":0,"output_tokens":0,"model":None}
        self.kb.side_effect=retrieval
        self.assertEqual(self.upload().status_code,409)
        self.completion.assert_not_called();self.synthesize.assert_not_called()
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),2)
        self.assertFalse(has_voice_scope())

    def test_actual_long_answer_continuation_is_blocked_after_first_call_expires(self):
        self.transcribe.return_value="Write a detailed explanation in 1200 words about opening hours."
        def completion(**kwargs):
            self.clock=self.session.deadline_at
            response=self.response("A short first segment.")
            response.choices[0]["finish_reason"]="length"
            return response
        self.completion.side_effect=completion
        self.assertEqual(self.upload().status_code,409)
        self.assertEqual(self.completion.call_count,1)
        self.synthesize.assert_not_called()
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),2)
        self.client.get(f"/api/live-voice/{self.session.public_id}/")
        self.client.post(f"/api/live-voice/{self.session.public_id}/stop/")
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(600000,0))
        self.assertEqual(self.upload().status_code,404)
        self.assertEqual(self.completion.call_count,1)

    def test_actual_domain_review_cannot_make_second_call_after_deadline(self):
        self.bot.category="business";self.bot.save(update_fields=["category"])
        def classify(**kwargs):
            self.clock=self.session.deadline_at
            return self.response("OUT_OF_DOMAIN|This question is outside the category.")
        self.completion.side_effect=classify
        with patch("ai_assistant.bots.chat_service.check_message_domain",side_effect=knowledge_utils.check_message_domain):
            self.assertEqual(self.upload().status_code,409)
        self.assertEqual(self.completion.call_count,1)
        self.synthesize.assert_not_called()

    def test_completed_response_and_replay_keep_history_and_debit_once(self):
        self.assertEqual(self.upload().json()["result"]["state"],"completed")
        self.assertEqual(self.upload().json()["result"]["state"],"completed")
        self.assertEqual(self.completion.call_count,1)
        self.assertEqual(self.synthesize.call_count,1)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_message_count,1)
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),4)
        self.assertFalse(has_voice_scope())

    def test_slow_authorization_cannot_outlive_the_final_clock_check(self):
        self.processing();create=Mock()
        def entitlement(**kwargs):
            self.clock=self.session.deadline_at
            return self.user.profile
        with self.scope(),patch("ai_assistant.voice.live_free_entitlement.require_free_voice_access",side_effect=entitlement):
            with self.assertRaises(VoiceAccessDenied): provider_boundary.provider_call(create)
        create.assert_not_called()
