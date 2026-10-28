class TTSError(Exception):
    """Safe internal error code; never carries provider secrets or input text."""


class AuthorizationDenied(TTSError):
    pass


class InvalidInput(TTSError):
    pass


class Conflict(TTSError):
    pass


class NotProcessed(TTSError):
    """Mock confirms synthesis never started."""
