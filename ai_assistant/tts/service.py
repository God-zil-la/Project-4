from dataclasses import dataclass
from functools import wraps
import time

from django.db import connection, OperationalError, transaction
from django.db.models import F

from .authorization import authorize
from .errors import Conflict, NotProcessed, TTSError
from .models import TTSAccount, TTSRequest
from .provider import MockProvider
from .validation import validate


@dataclass(frozen=True)
class Result:
    request_id: object
    state: str
    audio: bytes | None = None
    format: str = 'mp3'
    mock: bool = True


def atomic(function):
    @wraps(function)
    def call(*args, **kwargs):
        if connection.in_atomic_block:
            raise TTSError('outer_transaction_forbidden')
        for attempt in range(6):
            try:
                with transaction.atomic():
                    return function(*args, **kwargs)
            except OperationalError as exc:
                if connection.vendor != 'sqlite' or 'locked' not in str(exc).lower() or attempt == 5:
                    raise
                time.sleep(.01 * (attempt + 1))
    return call


def lock_account(user_id):
    TTSAccount.objects.get_or_create(user_id=user_id)
    TTSAccount.objects.filter(user_id=user_id).update(lock_version=F('lock_version') + 1)
    return TTSAccount.objects.get(user_id=user_id)


@atomic
def prepare(*, user, assistant_id, text, request_id):
    key, fingerprint = validate(text=text, assistant_id=assistant_id, request_id=request_id)
    user_id = authorize(user, assistant_id)
    account = lock_account(user_id)
    authorize(user, assistant_id)  # Check again after lock wait.
    row = TTSRequest.objects.filter(account=account, request_id=key).first()
    if row:
        if row.fingerprint != fingerprint or row.assistant_id != assistant_id:
            raise Conflict('request_key_reused')
        return row
    return TTSRequest.objects.create(account=account, assistant_id=assistant_id,
                                     request_id=key, fingerprint=fingerprint)


@atomic
def claim(*, user, assistant_id, row_id):
    user_id = authorize(user, assistant_id)
    account = lock_account(user_id)
    authorize(user, assistant_id)
    row = TTSRequest.objects.get(pk=row_id, account=account, assistant_id=assistant_id)
    if row.state != 'pending':
        return False
    row.state = 'dispatched'
    row.save(update_fields=['state', 'updated_at'])
    return True


@atomic
def finish(*, user_id, row_id, state):
    """Internal outcome recording; never a client-accessible API or quota charge.

    Revocation after dispatch must not prevent recording the provider outcome.
    """
    if state not in {'succeeded', 'not_processed', 'uncertain'}:
        raise Conflict('invalid_outcome')
    account = lock_account(user_id)
    row = TTSRequest.objects.get(pk=row_id, account=account)
    if row.state in {'succeeded', 'not_processed'}:
        if row.state != state:
            raise Conflict('already_finalized')
        return row
    if row.state not in {'dispatched', 'uncertain'}:
        raise Conflict('not_dispatched')
    row.state = state
    row.save(update_fields=['state', 'updated_at'])
    return row


def synthesize(*, user, assistant_id, text, request_id):
    """Mock-only entry point. Audio returned once in memory, never persisted.

    Replays return status without audio; a lost response never triggers synthesis.
    A crash after claim leaves dispatched, requiring explicit future reconciliation.
    """
    row = prepare(user=user, assistant_id=assistant_id, text=text, request_id=request_id)
    if not claim(user=user, assistant_id=assistant_id, row_id=row.pk):
        row.refresh_from_db()
        return Result(row.request_id, row.state)
    try:
        audio = MockProvider().synthesize(text)
        if not isinstance(audio, bytes) or not audio:
            raise TTSError('invalid_mock_response')
    except NotProcessed:
        finish(user_id=user.pk, row_id=row.pk, state='not_processed')
        return Result(row.request_id, 'not_processed')
    except Exception:
        finish(user_id=user.pk, row_id=row.pk, state='uncertain')
        return Result(row.request_id, 'uncertain')
    finish(user_id=user.pk, row_id=row.pk, state='succeeded')
    # Do not deliver audio after an observed entitlement/ownership revocation.
    authorize(user, assistant_id)
    return Result(row.request_id, 'succeeded', audio)
