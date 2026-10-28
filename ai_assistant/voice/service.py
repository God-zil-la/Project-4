import re
import uuid

from django.db import IntegrityError, transaction

from ai_assistant.bots.models import Conversation
from .models import VoiceSession, VoiceTurn
from datetime import timedelta
from django.utils import timezone


class VoiceError(Exception):
    pass


class VoiceAccessDenied(VoiceError):
    pass


class VoiceConflict(VoiceError):
    pass


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise VoiceAccessDenied("Invalid identifier.") from None



VOICE_SESSION_MAX_AGE = timedelta(hours=24)


@transaction.atomic
def stop_session(*, user, session_id, expired_only=False):
    # Serialize starts and settlement in the same account lock order.
    from ai_assistant.accounts.models import UserProfile
    from .live_quota_service import _settle_session_free_voice
    from .live_session_timer import finalized_charge
    UserProfile.objects.select_for_update().get(user_id=user.pk)
    session = VoiceSession.objects.select_for_update().filter(
        public_id=_uuid(session_id), user=user, conversation__user=user,
    ).first()
    if session is None:
        raise VoiceAccessDenied("Voice session not found.")
    now = timezone.now()
    deadline = min(session.deadline_at or session.created_at + VOICE_SESSION_MAX_AGE, session.created_at + VOICE_SESSION_MAX_AGE)
    if not session.active or (expired_only and now < deadline):
        return session
    ended = max(session.started_at, min(now, deadline)) if session.started_at else min(now, deadline)
    if session.quota_reservation_id:
        reservation = session.quota_reservation
        _settle_session_free_voice(user=user, request_id=reservation.request_id,
            consumed_ms=finalized_charge(started_at=session.started_at,
                reserved_ms=reservation.duration_ms, ended_at=ended,
                monthly_period_end=reservation.usage.period_end))
    session.active = False
    session.ended_at = ended
    session.save(update_fields=["active", "ended_at"])
    return session


def expire_voice_session(*, user, session_id):
    was_active = VoiceSession.objects.filter(public_id=_uuid(session_id), user=user, active=True).exists()
    session = stop_session(user=user, session_id=session_id, expired_only=True)
    return int(was_active and not session.active)


def reconcile_expired_sessions(*, user):
    for identity in VoiceSession.objects.filter(user=user, active=True,
            deadline_at__lte=timezone.now()).values_list("public_id", flat=True):
        stop_session(user=user, session_id=identity, expired_only=True)


def _session(user, session_id, *, lock=False):
    query = VoiceSession.objects.select_related(
        "assistant", "conversation"
    )
    if lock:
        query = query.select_for_update()

    session = query.filter(
        public_id=_uuid(session_id),
        user=user,
        user__is_active=True,
        active=True,
    ).first()

    if session is None:
        raise VoiceAccessDenied("Voice session not found.")


    if (session.deadline_at is not None and timezone.now() >= session.deadline_at) or session.created_at <= timezone.now() - VOICE_SESSION_MAX_AGE:
        raise VoiceAccessDenied("Voice session expired.")


    if (
        session.conversation.user_id != user.pk
        or session.conversation.bot_id != session.assistant_id
        or session.conversation.is_widget
        or session.conversation.discord_integration_id is not None
        or session.assistant.owner_id != user.pk
    ):
        raise VoiceAccessDenied("Invalid voice session.")

    return session


@transaction.atomic
def start_session(*, user, assistant, conversation, request_id=None):
    if (
        assistant.owner_id != user.pk
        or conversation.user_id != user.pk
        or conversation.bot_id != assistant.pk
        or conversation.is_widget
        or conversation.discord_integration_id is not None
    ):
        raise VoiceAccessDenied("Invalid conversation.")

    from ai_assistant.accounts.models import UserProfile
    from .live_free_entitlement import require_free_voice_access, FreeVoiceAccessDenied
    from .live_quota_models import LiveVoiceMonthlyUsage
    from .live_quota_policy import free_monthly_period, remaining_free_ms
    from .live_quota_service import reserve_free_voice, LiveVoiceQuotaExceeded, LiveVoiceQuotaConflict
    from .live_session_timer import timer_snapshot
    try:
        UserProfile.objects.select_for_update().get(user_id=user.pk)
        require_free_voice_access(user=user)
        identity = _uuid(request_id) if request_id is not None else uuid.uuid4()
        if request_id is not None:
            existing = VoiceSession.objects.filter(
                user=user, quota_reservation__request_id=identity,
            ).first()
            if existing is not None:
                if (existing.assistant_id != assistant.pk or
                        existing.conversation_id != conversation.pk):
                    raise VoiceConflict("start_request_context_conflict")
                # A retry never creates a reservation or extends a deadline.
                return stop_session(user=user, session_id=existing.public_id, expired_only=True)
        reconcile_expired_sessions(user=user)
        now = timezone.now()
        start, end = free_monthly_period(now)
        usage, _ = LiveVoiceMonthlyUsage.objects.get_or_create(
            user=user, period_start=start, defaults={"period_end": end})
        duration = remaining_free_ms(used_ms=usage.used_ms, reserved_ms=usage.reserved_ms)
        if duration <= 0:
            raise VoiceConflict("monthly_free_voice_quota_exceeded")
        reservation = reserve_free_voice(user=user, request_id=identity, duration_ms=duration, observed_at=now)
        timer = timer_snapshot(started_at=now, reserved_ms=duration, observed_at=now, monthly_period_end=end)
        return VoiceSession.objects.create(user=user, assistant=assistant,
            conversation=conversation, quota_reservation=reservation,
            started_at=now, deadline_at=timer.deadline_at)
    except (FreeVoiceAccessDenied, UserProfile.DoesNotExist) as exc:
        raise VoiceAccessDenied("Free voice access denied.") from exc
    except (LiveVoiceQuotaExceeded, LiveVoiceQuotaConflict) as exc:
        raise VoiceConflict(str(exc)) from exc


@transaction.atomic
def reserve_turn(*, user, session_id, request_id, audio_sha256):
    session = _session(user, session_id, lock=True)
    request_id = _uuid(request_id)

    if not re.fullmatch(r"[0-9a-f]{64}", str(audio_sha256)):
        raise VoiceAccessDenied("Invalid audio fingerprint.")

    existing = VoiceTurn.objects.filter(
        session=session, request_id=request_id
    ).first()

    if existing is not None:
        if existing.audio_sha256 != audio_sha256:
            raise VoiceConflict("Request audio mismatch.")
        return existing, False

    try:
        with transaction.atomic():
            turn = VoiceTurn.objects.create(
                session=session,
                request_id=request_id,
                audio_sha256=audio_sha256,
            )
    except IntegrityError:
        existing = VoiceTurn.objects.get(
            session=session, request_id=request_id
        )
        if existing.audio_sha256 != audio_sha256:
            raise VoiceConflict("Request audio mismatch.")
        return existing, False

    return turn, True

ALLOWED_TRANSITIONS = {
    VoiceTurn.State.CREATED: {VoiceTurn.State.TRANSCRIBING},
    VoiceTurn.State.TRANSCRIBING: {
        VoiceTurn.State.TRANSCRIBED,
        VoiceTurn.State.FAILED,
        VoiceTurn.State.UNCERTAIN,
    },
    VoiceTurn.State.TRANSCRIBED: {VoiceTurn.State.PROCESSING},
    VoiceTurn.State.PROCESSING: {
        VoiceTurn.State.ANSWER_SAVED,
        VoiceTurn.State.FAILED,
        VoiceTurn.State.UNCERTAIN,
    },
    VoiceTurn.State.ANSWER_SAVED: {VoiceTurn.State.SYNTHESIZING},
    VoiceTurn.State.SYNTHESIZING: {
        VoiceTurn.State.COMPLETED,
        VoiceTurn.State.FAILED,
        VoiceTurn.State.UNCERTAIN,
    },
}


@transaction.atomic
def advance_turn(*, user, session_id, request_id, expected, target):
    if target == VoiceTurn.State.ANSWER_SAVED:
        raise VoiceConflict("AI answer must be saved atomically.")

    session = _session(user, session_id, lock=True)
    turn = VoiceTurn.objects.select_for_update().filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.state != expected:
        raise VoiceConflict("Voice turn state changed.")

    if target not in ALLOWED_TRANSITIONS.get(turn.state, set()):
        raise VoiceConflict("Illegal voice turn transition.")

    turn.state = target
    turn.save(update_fields=["state", "updated_at"])
    return turn


@transaction.atomic
def attach_saved_answer(
    *, user, session_id, request_id, message_id
):
    from ai_assistant.bots.models import ChatMessage

    session = _session(user, session_id, lock=True)

    turn = VoiceTurn.objects.select_for_update().filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    message = ChatMessage.objects.filter(
        pk=message_id,
        user_id=user.pk,
        bot_id=session.assistant_id,
        conversation_id=session.conversation_id,
        sender=ChatMessage.SENDER_ASSISTANT,
    ).first()

    if message is None:
        raise VoiceAccessDenied("Assistant message not found.")

    if turn.assistant_message_id is not None:
        if turn.assistant_message_id != message.pk:
            raise VoiceConflict("Different answer already attached.")
        if turn.state != VoiceTurn.State.ANSWER_SAVED:
            raise VoiceConflict("Unexpected turn state.")
        return turn, False

    if turn.state != VoiceTurn.State.PROCESSING:
        raise VoiceConflict("Turn is not awaiting an answer.")

    turn.assistant_message = message
    turn.state = VoiceTurn.State.ANSWER_SAVED
    turn.save(update_fields=[
        "assistant_message", "state", "updated_at"
    ])

    return turn, True



@transaction.atomic
def claim_ai_dispatch(*, user, session_id, request_id):
    session = _session(user, session_id, lock=True)

    turn = VoiceTurn.objects.select_for_update().filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.assistant_message_id is not None:
        return turn, False

    if turn.state != VoiceTurn.State.TRANSCRIBED:
        return turn, False

    turn.state = VoiceTurn.State.PROCESSING
    turn.save(update_fields=["state", "updated_at"])
    return turn, True



@transaction.atomic
def save_transcript(*, user, session_id, request_id, transcript):
    if not isinstance(transcript, str):
        raise VoiceConflict("Invalid transcript.")

    transcript = transcript.strip()

    if not transcript or len(transcript) > 10000:
        raise VoiceConflict("Invalid transcript length.")

    session = _session(user, session_id, lock=True)

    turn = VoiceTurn.objects.select_for_update().filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.state == VoiceTurn.State.TRANSCRIBED:
        if turn.transcript != transcript:
            raise VoiceConflict("Conflicting transcript.")
        return turn, False

    if turn.state != VoiceTurn.State.TRANSCRIBING:
        raise VoiceConflict("Voice turn not transcribing.")

    turn.transcript = transcript
    turn.state = VoiceTurn.State.TRANSCRIBED
    turn.save(update_fields=["transcript", "state", "updated_at"])
    return turn, True



@transaction.atomic
def claim_tts_dispatch(*, user, session_id, request_id):
    session = _session(user, session_id, lock=True)

    turn = VoiceTurn.objects.select_for_update().filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.assistant_message_id is None:
        raise VoiceConflict("No saved AI answer.")

    if turn.state != VoiceTurn.State.ANSWER_SAVED:
        return turn, False

    turn.state = VoiceTurn.State.SYNTHESIZING
    turn.save(update_fields=["state", "updated_at"])

    return turn, True
