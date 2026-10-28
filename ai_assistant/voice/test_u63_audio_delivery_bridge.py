"""U6.3 audio delivery identity and storage regression tests."""

from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings

from .audio_store_bridge import (
    build_voice_audio_store,
    retrieve_voice_audio,
)
from .local_audio_store import LocalVoiceAudioStore
from .real_tts_identity import validate_real_tts_identity


class U63AudioDeliveryBridgeTests(SimpleTestCase):

    def test_real_tts_identity_preserves_voice_request_uuid(self):
        voice_request_id = uuid4()

        key, fingerprint = validate_real_tts_identity(
            text="Hello from the assistant.",
            assistant_id=1,
            conversation_id=uuid4(),
            message_id=10,
            request_id=voice_request_id,
        )

        self.assertEqual(key, voice_request_id)
        self.assertEqual(len(fingerprint), 64)

    @override_settings(DEBUG=True)
    @patch.dict(
        "os.environ",
        {"U63_LOCAL_LIVE_VOICE_ENABLED": "true"},
    )
    def test_local_store_is_bound_to_authenticated_user_id(self):
        user = Mock()
        user.pk = 123

        store = build_voice_audio_store(user=user)

        self.assertIsInstance(store, LocalVoiceAudioStore)
        self.assertEqual(store.user_id, 123)

    @override_settings(DEBUG=False)
    @patch.dict(
        "os.environ",
        {"U63_LOCAL_LIVE_VOICE_ENABLED": "true"},
    )
    def test_local_store_is_not_selected_outside_debug(self):
        user = Mock()
        user.pk = 123

        with override_settings(
            U62_CLEANUP_ENABLED=False,
            U62_R2_ENABLED=False,
        ):
            store = build_voice_audio_store(user=user)

        self.assertIsNone(store)

    @patch(
        "ai_assistant.voice.audio_store_bridge.retrieve_audio"
    )
    @patch(
        "ai_assistant.voice.audio_store_bridge.build_voice_audio_store"
    )
    def test_retrieval_uses_same_voice_uuid_and_user(
        self,
        mock_build_store,
        mock_retrieve,
    ):
        user = Mock()
        user.pk = 123
        store = Mock()
        request_id = uuid4()
        audio = b"ID3" + b"\x00" * 16

        mock_build_store.return_value = store
        mock_retrieve.return_value = audio

        result = retrieve_voice_audio(
            user=user,
            assistant_id=1,
            voice_request_id=request_id,
        )

        self.assertEqual(result, audio)
        mock_build_store.assert_called_once_with(user=user)
        mock_retrieve.assert_called_once_with(
            user=user,
            assistant_id=1,
            request_id=request_id,
            store=store,
        )

    @patch(
        "ai_assistant.voice.audio_store_bridge.build_voice_audio_store"
    )
    @patch(
        "ai_assistant.voice.audio_store_bridge.retrieve_audio"
    )
    def test_missing_store_fails_closed(
        self,
        mock_retrieve,
        mock_build_store,
    ):
        mock_build_store.return_value = None

        result = retrieve_voice_audio(
            user=Mock(pk=123),
            assistant_id=1,
            voice_request_id=uuid4(),
        )

        self.assertIsNone(result)
        mock_retrieve.assert_not_called()
