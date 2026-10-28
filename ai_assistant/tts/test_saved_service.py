"""Transactional security tests for saved-response preparation."""
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from . import authorization, saved_service
from .errors import AuthorizationDenied, Conflict
from .models import TTSRequest


class SavedServiceTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='saved-owner')
        self.args = {
            'user': self.user,
            'assistant_id': 7,
            'conversation_id': uuid4(),
            'message_id': 42,
            'request_id': uuid4(),
        }
        self.plan = 'premium'
        self.owned = True

        plan_patch = patch.object(
            authorization, '_effective_plan',
            side_effect=lambda _: self.plan,
        )
        owner_patch = patch.object(
            authorization, '_owns_assistant',
            side_effect=lambda *_: self.owned,
        )
        plan_patch.start()
        owner_patch.start()
        self.addCleanup(plan_patch.stop)
        self.addCleanup(owner_patch.stop)

    def test_prepares_one_request_without_synthesis(self):
        with patch.object(
            saved_service, 'get_assistant_message',
            return_value='Saved assistant answer',
        ) as lookup:
            first = saved_service.prepare_saved_response(**self.args)

        self.assertEqual(first.state, 'pending')
        self.assertEqual(TTSRequest.objects.count(), 1)
        self.assertEqual(lookup.call_count, 2)

    def test_identical_replay_returns_existing_request(self):
        with patch.object(
            saved_service, 'get_assistant_message',
            return_value='Same answer',
        ):
            first = saved_service.prepare_saved_response(**self.args)
            second = saved_service.prepare_saved_response(**self.args)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(TTSRequest.objects.count(), 1)

    def test_different_message_or_conversation_conflicts(self):
        with patch.object(
            saved_service, 'get_assistant_message',
            return_value='Identical text',
        ):
            saved_service.prepare_saved_response(**self.args)

            for change in (
                {'message_id': 43},
                {'conversation_id': uuid4()},
            ):
                with self.subTest(change=change):
                    with self.assertRaises(Conflict):
                        saved_service.prepare_saved_response(
                            **(self.args | change)
                        )

        self.assertEqual(TTSRequest.objects.count(), 1)

    def test_changed_text_conflicts(self):
        with patch.object(
            saved_service, 'get_assistant_message',
            side_effect=[
                'Original', 'Original',
                'Changed', 'Changed',
            ],
        ):
            saved_service.prepare_saved_response(**self.args)
            with self.assertRaises(Conflict):
                saved_service.prepare_saved_response(**self.args)

        self.assertEqual(TTSRequest.objects.count(), 1)

    def test_text_change_during_preparation_rolls_back(self):
        with patch.object(
            saved_service, 'get_assistant_message',
            side_effect=['Before lock', 'After lock'],
        ):
            with self.assertRaises(Conflict):
                saved_service.prepare_saved_response(**self.args)

        self.assertEqual(TTSRequest.objects.count(), 0)

    def test_revocation_after_lock_rolls_back(self):
        def revoke(user_id):
            account = original_lock(user_id)
            self.plan = 'free'
            return account

        original_lock = saved_service.service.lock_account

        with patch.object(
            saved_service, 'get_assistant_message',
            return_value='Private answer',
        ), patch.object(
            saved_service.service, 'lock_account',
            side_effect=revoke,
        ):
            with self.assertRaises(AuthorizationDenied):
                saved_service.prepare_saved_response(**self.args)

        self.assertEqual(TTSRequest.objects.count(), 0)
