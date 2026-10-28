"""Mock-only synthesis of authorized, saved assistant responses."""

from . import service
from .errors import Conflict, NotProcessed, TTSError
from .audio_pipeline import store_synthesized_audio
from .message_access import get_assistant_message
from .message_identity import validate_saved_response
from .provider import MockProvider
from .saved_service import prepare_saved_response


def synthesize_saved_response(*, user, assistant_id, conversation_id, message_id, request_id, audio_store=None):
    row = prepare_saved_response(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    if not service.claim(user=user, assistant_id=assistant_id, row_id=row.pk):
        row.refresh_from_db()
        return service.Result(row.request_id, row.state)

    # The committed dispatch claim must exist before any provider call.
    try:
        text = get_assistant_message(
            user=user,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        _, current_fingerprint = validate_saved_response(
            text=text,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
        )
        if current_fingerprint != row.fingerprint:
            service.finish(user_id=user.pk, row_id=row.pk, state='not_processed')
            raise Conflict('message_changed')
    except Conflict:
        raise
    except Exception:
        service.finish(user_id=user.pk, row_id=row.pk, state='not_processed')
        raise

    try:
        audio = MockProvider().synthesize(text)
        if not isinstance(audio, bytes) or not audio:
            raise TTSError('invalid_mock_response')
    except NotProcessed:
        service.finish(user_id=user.pk, row_id=row.pk, state='not_processed')
        return service.Result(row.request_id, 'not_processed')
    except Exception:
        service.finish(user_id=user.pk, row_id=row.pk, state='uncertain')
        return service.Result(row.request_id, 'uncertain')

    if audio_store is not None:
        # Verify the saved message again before persisting potentially stale audio.
        try:
            current_text = get_assistant_message(
                user=user, assistant_id=assistant_id,
                conversation_id=conversation_id, message_id=message_id,
            )
            _, fingerprint = validate_saved_response(
                text=current_text, assistant_id=assistant_id,
                conversation_id=conversation_id, message_id=message_id,
                request_id=request_id,
            )
            if fingerprint != row.fingerprint:
                raise Conflict('message_changed')
        except Exception:
            service.finish(user_id=user.pk, row_id=row.pk, state='uncertain')
            raise

    if audio_store is None:
        service.finish(user_id=user.pk, row_id=row.pk, state='succeeded')
    else:
        store_synthesized_audio(
            user_id=user.pk,
            row_id=row.pk,
            request_id=row.request_id,
            audio=audio,
            store=audio_store,
        )

    # Do not release audio after access or entitlement is revoked.
    current_text = get_assistant_message(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    _, current_fingerprint = validate_saved_response(
        text=current_text,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )
    if current_fingerprint != row.fingerprint:
        raise Conflict('message_changed')

    return service.Result(row.request_id, 'succeeded', audio)


def recover_saved_response(*, user, assistant_id, conversation_id, message_id,
                           request_id, audio_store):
    """Explicit recovery of retained bytes; never calls a synthesis provider.

    Missing/expired audio leaves state unchanged and does not renew its TTL.
    Only trusted backend code may call this; it is not a public endpoint.
    """
    from .audio_storage import validate_audio
    from .audio_retrieval import retrieve_audio

    args = dict(user=user, assistant_id=assistant_id,
                conversation_id=conversation_id, message_id=message_id,
                request_id=request_id)
    row = prepare_saved_response(**args)
    if row.state not in {'dispatched', 'uncertain', 'succeeded'}:
        return service.Result(row.request_id, row.state)
    audio = audio_store.load(request_id=row.pk)
    if audio is None:
        return service.Result(row.request_id, row.state)
    validate_audio(audio)
    # Recheck message identity and rights after storage I/O.
    prepare_saved_response(**args)
    service.finish(user_id=user.pk, row_id=row.pk, state='succeeded')
    audio = retrieve_audio(user=user, assistant_id=assistant_id,
                           request_id=row.request_id, store=audio_store)
    return service.Result(row.request_id, 'succeeded', audio)
