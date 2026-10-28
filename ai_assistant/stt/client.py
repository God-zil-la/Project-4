"""Isolated HTTP transport; no OpenAI SDK imports or global configuration changes."""
import json
import time

import requests

URL = 'https://api.openai.com/v1/audio/transcriptions'
MODEL = 'gpt-transcribe'
MAX_RESPONSE_BYTES = 1_000_000


class TranscriptionError(Exception):
    def __init__(self, code, *, uncertain=False):
        super().__init__(code)
        self.code = code
        # Timeouts/network errors MUST NOT cause blind quota release/retry.
        self.uncertain = uncertain


def transcribe(audio, *, api_key):
    """Call only after authenticated entitlement checking and durable reservation.

    Socket timeouts are not a hard wall-clock deadline. The eventual endpoint
    still requires a cancellable worker deadline; this module is not exposed.
    """
    if not api_key:
        raise TranscriptionError('stt_unconfigured')
    audio.file.seek(0)
    started = time.monotonic()
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.post(
                URL,
                headers={'Authorization': 'Bearer ' + api_key},
                files={'file': ('audio.wav', audio.file, 'audio/wav')},
                data={'model': MODEL, 'response_format': 'json'},
                timeout=(5, 45), allow_redirects=False, stream=True,
            ) as response:
                if response.status_code != 200:
                    raise TranscriptionError('stt_provider_error', uncertain=True)
                body = bytearray()
                for block in response.iter_content(chunk_size=8192):
                    if time.monotonic() - started > 50:
                        raise TranscriptionError('stt_timeout', uncertain=True)
                    body.extend(block)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise TranscriptionError('stt_invalid_response', uncertain=True)
                try:
                    result = json.loads(body)
                except (ValueError, UnicodeError) as exc:
                    raise TranscriptionError('stt_invalid_response', uncertain=True) from exc
                if not isinstance(result, dict) or not isinstance(result.get('text'), str):
                    raise TranscriptionError('stt_invalid_response', uncertain=True)
                return result['text']
    except requests.Timeout as exc:
        raise TranscriptionError('stt_timeout', uncertain=True) from exc
    except requests.RequestException as exc:
        raise TranscriptionError('stt_unavailable', uncertain=True) from exc
