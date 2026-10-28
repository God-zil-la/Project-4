"""No network client, API key, model, voice, or real synthesis exists here."""


class MockProvider:
    def synthesize(self, text):
        # Deliberately NOT a playable MP3. Transport plumbing fixture only.
        return b'U62-MOCK-AUDIO-NOT-REAL-MP3'
