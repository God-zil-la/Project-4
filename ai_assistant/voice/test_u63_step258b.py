"""U6.3 step 258B: real MP3 recovery with isolated storage."""

import os
from pathlib import Path
from unittest.mock import patch

from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.real_audio_recovery import (
    recover_real_voice_audio,
)
from ai_assistant.voice.test_u63_step254 import (
    Step254RealDatabaseTests,
)


class IsolatedAudioStore:
    def __init__(self):
        self.audio = {}
        self.loads = 0

    def save(self, *, request_id, audio):
        self.audio[request_id] = audio

    def load(self, *, request_id):
        self.loads += 1
        return self.audio.get(request_id)


class Step258BRealMP3Tests(Step254RealDatabaseTests):
    """Use the existing real ORM fixture, with genuine MP3 bytes."""

    def setUp(self):
        super().setUp()
        self.real_mp3 = Path(
            os.environ["U63_STEP258A_MP3"]
        ).read_bytes()
        self.store = IsolatedAudioStore()
        self.store.save(
            request_id=self.tts_request.pk,
            audio=self.real_mp3,
        )

    def test_09_real_mp3_recovery(self):
        with (
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "get_assistant_message",
                return_value=self.message.message,
            ),
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "retrieve_audio",
                return_value=self.store.load(
                    request_id=self.tts_request.pk,
                ),
            ),
        ):
            result = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.store,
            )

        self.turn.refresh_from_db()
        self.assertTrue(result.audio_available)
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.COMPLETED,
        )
        self.assertEqual(
            self.store.audio[self.tts_request.pk],
            self.real_mp3,
        )

    def test_10_recovery_does_not_synthesize(self):
        with (
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "get_assistant_message",
                return_value=self.message.message,
            ),
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "retrieve_audio",
                return_value=self.real_mp3,
            ),
            patch(
                "ai_assistant.voice.real_tts_integration."
                "execute_isolated_live_tts",
                side_effect=AssertionError(
                    "Unexpected synthesis"
                ),
                create=True,
            ),
        ):
            result = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.store,
            )

        self.assertTrue(result.audio_available)
