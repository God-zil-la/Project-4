"""Block E: actual chat engine, local STT/TTS and zero external network."""
import io
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import openai
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from ai_assistant.bots.models import Bot, ChatMessage, Conversation
from .free_voice_chain import VoiceChainProviders, voice_chain_providers
from .live_quota_models import LiveVoiceMonthlyUsage
from .models import VoiceTurn
from .service import start_session
from .test_upload_api import sample_wav


@override_settings(DEBUG=True, U63_VOICE_TEST_DOUBLES=True)
class BlockEChainTests(TestCase):
    def setUp(self):
        cache.clear()
        fake_key = patch.dict(os.environ, {"OPENAI_API_KEY":"block-e-local-test-placeholder"})
        fake_key.start(); self.addCleanup(fake_key.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        config = override_settings(BASE_DIR=Path(self.temp.name))
        config.enable(); self.addCleanup(config.disable)
        self.user = get_user_model().objects.create_user(username="block_e_owner")
        self.other = get_user_model().objects.create_user(username="block_e_other")
        self.bot = Bot.objects.create(owner=self.user, name="Voice Guide", category="general",
            personality="Be calm and precise. Use the configured reference material.",
            description="The owner configured this assistant.", knowledge_activation_mode="always")
        self.conversation = Conversation.objects.create(user=self.user, bot=self.bot)
        ChatMessage.objects.create(user=self.user, bot=self.bot, conversation=self.conversation,
            sender=ChatMessage.SENDER_USER, message="Earlier conversation context")
        ChatMessage.objects.create(user=self.user, bot=self.bot, conversation=self.conversation,
            sender=ChatMessage.SENDER_ASSISTANT, message="Earlier saved answer")
        self.clock = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        time_patch = patch("django.utils.timezone.now", side_effect=lambda:self.clock)
        time_patch.start(); self.addCleanup(time_patch.stop)
        self.session = start_session(user=self.user, assistant=self.bot, conversation=self.conversation)
        self.client.force_login(self.user)
        self.request_id = str(uuid4())
        self.url = f"/api/live-voice/{self.session.public_id}/upload/"
        self.transcribe = Mock(return_value="What does the reference say about opening hours?")
        self.mp3 = Path(os.environ["U63_STEP258A_MP3"]).read_bytes()
        self.synthesize = Mock(return_value=self.mp3)
        self.providers = VoiceChainProviders(self.transcribe, self.synthesize, mock_ai=self.local_mock_ai)
        scope = voice_chain_providers(self.providers)
        scope.__enter__(); self.addCleanup(scope.__exit__, None, None, None)
        self.completion = Mock(side_effect=lambda **kwargs:self.response("The reference says we open at nine."))
        api = patch("openai.ChatCompletion.create", self.completion)
        api.start(); self.addCleanup(api.stop)
        kb = patch("ai_assistant.bots.chat_service.search_relevant_chunks", return_value={
            "chunks":["REFERENCE FACT: opening time is 09:00."], "sources":[],
            "tokens_used":0,"input_tokens":0,"output_tokens":0,"model":None})
        self.kb = kb.start(); self.addCleanup(kb.stop)
        domain = patch("ai_assistant.bots.chat_service.check_message_domain", return_value={
            "in_domain":True,"tokens_used":0,"input_tokens":0,"output_tokens":0,"model":None})
        domain.start(); self.addCleanup(domain.stop)
        network = patch("socket.socket.connect", side_effect=AssertionError("External network forbidden in Block E tests"))
        network.start(); self.addCleanup(network.stop)

    def local_mock_ai(self, **kwargs):
        if str(kwargs.get("model", "")).startswith("text-embedding"):
            return openai.Embedding.create(**kwargs)  # explicitly patched by embedding tests
        return self.completion(**kwargs)

    @staticmethod
    def response(text):
        return openai.util.convert_to_openai_object({"choices":[{"message":{"content":text},"finish_reason":"stop"}],
            "usage":{"prompt_tokens":10,"completion_tokens":10,"total_tokens":20},"model":"gpt-4o-mini"})

    def upload(self, request_id=None, wav=None):
        return self.client.post(self.url, {"request_id":request_id or self.request_id,"process_voice":"true",
            "audio":SimpleUploadedFile("voice.wav",wav or sample_wav(),content_type="audio/wav")})

    def turn_url(self):
        return f"/api/live-voice/{self.session.public_id}/turns/{self.request_id}/"

    def test_full_chain_uses_existing_engine_prompt_kb_and_history(self):
        response=self.upload()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["result"]["state"],"completed")
        turn=VoiceTurn.objects.get()
        self.assertEqual(turn.transcript,self.transcribe.return_value)
        self.assertEqual(turn.session_id,self.session.pk)
        self.assertEqual(turn.assistant_message.conversation_id,self.conversation.pk)
        messages=self.completion.call_args.kwargs["messages"]
        content="\n".join(m["content"] for m in messages)
        for expected in [self.bot.personality,self.bot.description,"REFERENCE FACT", "Earlier conversation context","Earlier saved answer",self.transcribe.return_value]:
            self.assertIn(expected,content)
        self.assertEqual(self.kb.call_args.args[0].pk,self.bot.pk)
        self.assertEqual(self.synthesize.call_args.args[0],turn.assistant_message.message)
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),4)
        audio=self.client.get(self.turn_url()+"audio/")
        self.assertEqual(audio.status_code,200)
        self.assertEqual(audio.content,self.mp3)
        self.assertEqual(audio["Content-Type"],"audio/mpeg")
        self.assertEqual(audio["Cache-Control"],"private, no-store")

    def test_retries_do_not_repeat_stt_ai_tts_or_chat_debits(self):
        first=self.upload(); second=self.upload()
        self.assertEqual(first.json()["result"],second.json()["result"])
        for provider in [self.transcribe,self.completion,self.synthesize]: self.assertEqual(provider.call_count,1)
        self.assertEqual(VoiceTurn.objects.count(),1)
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),4)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_message_count,1)
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(0,600000))

    def test_parallel_retry_observes_claim_without_dispatching_twice(self):
        results=[]
        def stt(audio):
            results.append(self.upload().json()["result"]["state"])
            return "What are the opening hours?"
        self.transcribe.side_effect=stt
        self.assertEqual(self.upload().json()["result"]["state"],"completed")
        self.assertEqual(results,["transcribing"])
        for provider in [self.transcribe,self.completion,self.synthesize]: self.assertEqual(provider.call_count,1)

    def test_expiry_during_stt_prevents_ai_and_tts(self):
        def stt(audio):
            self.clock=self.session.deadline_at
            return "Transcribed too late"
        self.transcribe.side_effect=stt
        self.assertEqual(self.upload().status_code,409)
        self.completion.assert_not_called(); self.synthesize.assert_not_called()
        self.assertEqual(VoiceTurn.objects.get().state,"uncertain")
        self.client.get(f"/api/live-voice/{self.session.public_id}/")
        self.client.post(f"/api/live-voice/{self.session.public_id}/stop/")
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(600000,0))

    def test_expiry_during_ai_preserves_saved_history_but_blocks_tts(self):
        def answer(**kwargs):
            self.clock=self.session.deadline_at
            return self.response("This answer was saved despite the session ending.")
        self.completion.side_effect=answer
        self.assertEqual(self.upload().status_code,409)
        self.synthesize.assert_not_called()
        turn=VoiceTurn.objects.get()
        self.assertIsNotNone(turn.assistant_message_id)
        self.assertEqual(turn.state,"uncertain")
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),4)

    def test_expiry_during_tts_does_not_publish_audio(self):
        def tts(text):
            self.clock=self.session.deadline_at
            return self.mp3
        self.synthesize.side_effect=tts
        self.assertEqual(self.upload().status_code,409)
        turn=VoiceTurn.objects.get()
        self.assertIsNone(turn.output_audio_key)
        self.assertIsNotNone(turn.assistant_message_id)
        self.assertEqual(self.client.get(self.turn_url()+"audio/").status_code,404)

    def test_uncertain_tts_never_regenerates_on_retry(self):
        self.synthesize.side_effect=TimeoutError("Local simulated timeout")
        self.assertEqual(self.upload().json()["result"]["state"],"uncertain")
        self.assertEqual(self.upload().json()["result"]["state"],"uncertain")
        for provider in [self.transcribe,self.completion,self.synthesize]: self.assertEqual(provider.call_count,1)
        self.assertIsNotNone(VoiceTurn.objects.get().assistant_message_id)

    def test_owner_and_session_identity_are_enforced(self):
        self.client.force_login(self.other)
        self.assertEqual(self.upload().status_code,404)
        self.assertEqual(self.client.get(self.turn_url()+"audio/").status_code,404)
        self.client.force_login(self.user)
        self.url=f"/api/live-voice/{uuid4()}/upload/"
        self.assertEqual(self.upload().status_code,404)
        self.transcribe.assert_not_called()

    def test_disabled_and_external_providers_fail_before_any_dispatch(self):
        with override_settings(U63_VOICE_TEST_DOUBLES=False):
            self.assertEqual(self.upload().status_code,503)
        with voice_chain_providers(VoiceChainProviders(self.transcribe,self.synthesize,external_calls=True)):
            self.assertEqual(self.upload().status_code,503)
        self.transcribe.assert_not_called()
        self.assertEqual(VoiceTurn.objects.count(),0)

    def test_stopped_session_and_mismatched_audio_cannot_redispatch(self):
        self.upload()
        data=bytearray(sample_wav()); data[-1]=1
        self.assertEqual(self.upload(wav=bytes(data)).status_code,409)
        self.client.post(f"/api/live-voice/{self.session.public_id}/stop/")
        self.assertEqual(self.upload().status_code,404)
        for provider in [self.transcribe,self.completion,self.synthesize]: self.assertEqual(provider.call_count,1)

    def test_local_store_corruption_never_serves_wrong_audio(self):
        self.upload()
        turn=VoiceTurn.objects.get()
        path=Path(self.temp.name)/".u63_private_audio"/str(self.user.pk)/(str(turn.output_audio_key)+".mp3")
        path.write_bytes(b"ID3wrong response")
        self.assertEqual(self.client.get(self.turn_url()+"audio/").status_code,503)
        self.synthesize.assert_called_once()

    def test_missing_or_cancelled_recording_creates_no_turn(self):
        self.assertEqual(self.client.post(self.url,{"process_voice":"true","request_id":self.request_id}).status_code,400)
        self.assertFalse(VoiceTurn.objects.exists())
        self.transcribe.assert_not_called()

    def test_user_stop_during_transcription_prevents_follow_on_calls(self):
        def stt(audio):
            self.clock += timedelta(seconds=2)
            response=self.client.post(f"/api/live-voice/{self.session.public_id}/stop/")
            self.assertEqual(response.status_code,200)
            return "Cancelled speech"
        self.transcribe.side_effect=stt
        self.assertEqual(self.upload().status_code,409)
        self.completion.assert_not_called(); self.synthesize.assert_not_called()
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),2)
        usage=LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms,usage.reserved_ms),(2000,0))

    def test_next_voice_turn_inherits_the_previous_saved_exchange(self):
        self.assertEqual(self.upload().json()["result"]["state"],"completed")
        self.request_id=str(uuid4())
        self.transcribe.return_value="Please repeat the opening time from our previous answer."
        self.assertEqual(self.upload().json()["result"]["state"],"completed")
        messages=self.completion.call_args.kwargs["messages"]
        self.assertTrue(any(m["role"]=="assistant" and "open at nine" in m["content"] for m in messages))
        self.assertEqual(ChatMessage.objects.filter(conversation=self.conversation).count(),6)
        self.assertEqual(VoiceTurn.objects.count(),2)

    def test_different_parallel_turn_is_blocked_before_provider_dispatch(self):
        blocked=[]
        def stt(audio):
            blocked.append(self.upload(request_id=str(uuid4())).status_code)
            return "What are the opening hours?"
        self.transcribe.side_effect=stt
        self.assertEqual(self.upload().json()["result"]["state"],"completed")
        self.assertEqual(blocked,[409])
        self.assertEqual(VoiceTurn.objects.count(),1)
        for provider in [self.transcribe,self.completion,self.synthesize]: self.assertEqual(provider.call_count,1)
