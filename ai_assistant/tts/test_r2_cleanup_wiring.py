"""Offline factory-to-cleanup-command wiring checks. No R2 or DB I/O."""
import io
import sys
from types import ModuleType
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from .cleanup_factory import build_cleanup_dependencies


ENDPOINT = 'https://' + ('a' * 32) + '.r2.cloudflarestorage.com'
SETTINGS = {
    'U62_CLEANUP_ENABLED': True,
    'U62_R2_ENABLED': True,
    'U62_R2_BUCKET': 'isolated-test-bucket',
    'U62_R2_CLIENT_FACTORY': 'ai_assistant.tts.r2_client_factory.build_r2_client',
    'U62_R2_ENDPOINT_URL': ENDPOINT,
    'U62_R2_ACCESS_KEY_ID': 'offline-only-placeholder',
    'U62_R2_SECRET_ACCESS_KEY': 'offline-only-placeholder',
    'U62_GLOBAL_STORAGE_MAX_BYTES': 10485760,
    'U62_GLOBAL_STORAGE_MAX_OBJECTS': 100,
    'U62_GLOBAL_STORAGE_MAX_UPLOADS_PER_DAY': 500,
    'U62_ACCOUNT_STORAGE_MAX_BYTES': 1048576,
    'U62_ACCOUNT_STORAGE_MAX_OBJECTS': 10,
    'U62_ACCOUNT_STORAGE_MAX_UPLOADS_PER_DAY': 50,
}


def fake_boto_modules():
    boto3 = ModuleType('boto3')
    boto3.client = Mock(return_value=Mock(name='fake_r2_client'))
    botocore = ModuleType('botocore')
    config = ModuleType('botocore.config')
    config.Config = Mock(return_value=object())
    botocore.config = config
    return {'boto3': boto3, 'botocore': botocore, 'botocore.config': config}


class R2CleanupWiringTests(SimpleTestCase):
    def test_factory_resolves_real_client_factory_with_fake_boto(self):
        mocks = fake_boto_modules()
        with override_settings(**SETTINGS), patch.dict(sys.modules, mocks):
            repository, store = build_cleanup_dependencies()
        self.assertIs(store.client, mocks['boto3'].client.return_value)
        self.assertEqual(store.bucket, 'isolated-test-bucket')
        self.assertEqual(repository.account_limits.max_objects, 10)
        mocks['boto3'].client.assert_called_once()
        store.client.put_object.assert_not_called()
        store.client.get_object.assert_not_called()
        store.client.delete_object.assert_not_called()

    def test_cleanup_disabled_rejects_before_boto_import(self):
        mocks = fake_boto_modules()
        with override_settings(**{**SETTINGS, 'U62_CLEANUP_ENABLED': False}), patch.dict(sys.modules, mocks):
            with self.assertRaisesRegex(RuntimeError, 'cleanup_disabled'):
                build_cleanup_dependencies()
        mocks['boto3'].client.assert_not_called()

    def test_r2_disabled_rejects_before_boto_import(self):
        mocks = fake_boto_modules()
        with override_settings(**{**SETTINGS, 'U62_R2_ENABLED': False}), patch.dict(sys.modules, mocks):
            with self.assertRaisesRegex(RuntimeError, 'r2_disabled'):
                build_cleanup_dependencies()
        mocks['boto3'].client.assert_not_called()

    def test_dry_run_does_not_instantiate_client(self):
        mocks = fake_boto_modules()
        with override_settings(**{**SETTINGS, 'U62_CLEANUP_FACTORY': 'ai_assistant.tts.cleanup_factory.build_cleanup_dependencies'}), patch.dict(sys.modules, mocks):
            output = io.StringIO()
            call_command('tts_cleanup_once', stdout=output)
        self.assertIn('DRY RUN', output.getvalue())
        mocks['boto3'].client.assert_not_called()

    def test_execute_flag_not_enough_when_cleanup_disabled(self):
        mocks = fake_boto_modules()
        disabled = {**SETTINGS, 'U62_CLEANUP_ENABLED': False,
                    'U62_CLEANUP_FACTORY': 'ai_assistant.tts.cleanup_factory.build_cleanup_dependencies'}
        with override_settings(**disabled), patch.dict(sys.modules, mocks):
            with self.assertRaises(CommandError):
                call_command('tts_cleanup_once', '--execute')
        mocks['boto3'].client.assert_not_called()
