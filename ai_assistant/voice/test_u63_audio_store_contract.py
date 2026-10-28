from unittest import TestCase
from unittest.mock import patch

from ai_assistant.voice.local_audio_store import LocalVoiceAudioStore
from ai_assistant.voice.server_dependencies import (
    TrustedServerConfiguration,
    build_server_voice_dependencies,
)
from ai_assistant.voice.service import VoiceConflict


class AudioStoreDependencyContractTests(TestCase):

    @patch(
        "ai_assistant.voice.server_dependencies.make_real_stt_transcriber"
    )
    def test_local_audio_store_accepted(self, mock_transcriber):
        store = LocalVoiceAudioStore(user_id=123)

        configuration = TrustedServerConfiguration(
            resolve_evidence=lambda: None,
            reserve_stt=lambda: None,
            audio_store=store,
        )

        result = build_server_voice_dependencies(
            configuration=configuration,
            allow_paid_calls=False,
        )

        self.assertIs(result.audio_store, store)
        mock_transcriber.assert_called_once_with(
            allow_paid_calls=False
        )

    @patch(
        "ai_assistant.voice.server_dependencies.make_real_stt_transcriber"
    )
    def test_invalid_store_rejected(self, mock_transcriber):
        configuration = TrustedServerConfiguration(
            resolve_evidence=lambda: None,
            reserve_stt=lambda: None,
            audio_store=object(),
        )

        with self.assertRaises(VoiceConflict):
            build_server_voice_dependencies(
                configuration=configuration,
                allow_paid_calls=False,
            )

        mock_transcriber.assert_not_called()
