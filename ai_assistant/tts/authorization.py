from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import OperationalError, connection

from .errors import AuthorizationDenied


def _effective_plan(user_id):
    # Read the existing entitlement calculation; never reconstruct billing rules.
    profile = apps.get_model('accounts', 'UserProfile').objects.get(user_id=user_id)
    return profile.effective_plan


def _owns_assistant(user_id, assistant_id):
    return apps.get_model('bots', 'Bot').objects.filter(pk=assistant_id, owner_id=user_id).exists()


def authorize(user, assistant_id):
    """Trusted internal caller supplies the authenticated server principal.

    This is not an HTTP authenticator. Never deserialize a principal or a plan
    from request data. Fresh database reads happen on every check, including replay.
    """
    try:
        if (user.is_authenticated is not True or type(user.pk) is not int
                or user.pk <= 0 or type(assistant_id) is not int or assistant_id <= 0):
            raise AuthorizationDenied('tts_denied')
        fresh = get_user_model().objects.get(pk=user.pk)
        if (not fresh.is_active or _effective_plan(fresh.pk) not in {'premium', 'pro'}
                or not _owns_assistant(fresh.pk, assistant_id)):
            raise AuthorizationDenied('tts_denied')
        return fresh.pk
    except AuthorizationDenied:
        raise
    except OperationalError as exc:
        # Let the existing atomic SQLite retry handle transient lock errors.
        # Other database failures remain denied, without dispatching a provider.
        if connection.vendor == 'sqlite' and 'locked' in str(exc).lower():
            raise
        raise AuthorizationDenied('tts_denied') from exc
    except Exception as exc:
        # Missing models/profile, failed lookup or unavailable entitlement fails closed.
        raise AuthorizationDenied('tts_denied') from exc
