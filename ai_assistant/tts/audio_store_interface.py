"""Private audio storage interface for U6.2.

Storage implementations must enforce expiry and private access.
Authorization is checked separately before audio retrieval.
The request_id argument is the server-generated TTSRequest.pk, NEVER the
client request_id (which is unique only within an account).
Saves must be atomic and immutable during TTL; retries must not extend TTL.
"""

from typing import Protocol
from uuid import UUID


class AudioStore(Protocol):
    def save(self, *, request_id: UUID, audio: bytes) -> None:
        """Persist validated audio privately."""

    def load(self, *, request_id: UUID) -> bytes | None:
        """Return stored audio or None if missing or expired."""

    def delete(self, *, request_id: UUID) -> None:
        """Delete stored audio, if present."""
