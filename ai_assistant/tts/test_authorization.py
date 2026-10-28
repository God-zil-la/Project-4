from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from . import authorization
from .errors import AuthorizationDenied


class AuthorizationTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='owner')

    def test_existing_effective_plan_and_owner_lookup_contract(self):
        profile_model, bot_model = Mock(), Mock()
        profile_model.objects.get.return_value = SimpleNamespace(effective_plan='premium')
        bot_model.objects.filter.return_value.exists.return_value = True
        original = authorization.apps.get_model
        def resolve(*args, **kwargs):
            if args == ('accounts', 'UserProfile'):
                return profile_model
            if args == ('bots', 'Bot'):
                return bot_model
            return original(*args, **kwargs)
        with patch.object(authorization.apps, 'get_model', side_effect=resolve) as lookup:
            self.assertEqual(authorization.authorize(self.user, 7), self.user.pk)
        lookup.assert_any_call('accounts', 'UserProfile')
        lookup.assert_any_call('bots', 'Bot')
        profile_model.objects.get.assert_called_once_with(user_id=self.user.pk)
        bot_model.objects.filter.assert_called_once_with(pk=7, owner_id=self.user.pk)

    def test_premium_and_pro_only(self):
        with patch.object(authorization, '_owns_assistant', return_value=True):
            for plan in ('premium', 'pro', 'free', 'business', '', None):
                with self.subTest(plan=plan), patch.object(authorization, '_effective_plan', return_value=plan):
                    if plan in ('premium', 'pro'):
                        self.assertEqual(authorization.authorize(self.user, 1), self.user.pk)
                    else:
                        with self.assertRaises(AuthorizationDenied):
                            authorization.authorize(self.user, 1)

    def test_anonymous_inactive_and_deleted_user_denied(self):
        with self.assertRaises(AuthorizationDenied):
            authorization.authorize(AnonymousUser(), 1)
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        with self.assertRaises(AuthorizationDenied):
            authorization.authorize(self.user, 1)
        get_user_model().objects.filter(pk=self.user.pk).delete()
        with self.assertRaises(AuthorizationDenied):
            authorization.authorize(self.user, 1)

    def test_wrong_owner_denied(self):
        with patch.object(authorization, '_effective_plan', return_value='pro'), \
                patch.object(authorization, '_owns_assistant', return_value=False), \
                self.assertRaises(AuthorizationDenied):
            authorization.authorize(self.user, 7)

    def test_missing_integration_and_failed_entitlement_fail_closed(self):
        # Production models intentionally absent from standalone test settings.
        with self.assertRaises(AuthorizationDenied):
            authorization.authorize(self.user, 1)
        with patch.object(authorization, '_effective_plan', side_effect=RuntimeError('unavailable')), \
                self.assertRaises(AuthorizationDenied):
            authorization.authorize(self.user, 1)
