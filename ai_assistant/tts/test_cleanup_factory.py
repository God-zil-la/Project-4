"""Dependency factory safety tests. No external service access."""

from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from .cleanup_factory import build_cleanup_dependencies


VALID = {
    "U62_CLEANUP_ENABLED": True,
    "U62_R2_ENABLED": True,
    "U62_R2_BUCKET": "isolated-test-bucket",
    "U62_R2_CLIENT_FACTORY": "isolated.fake_client",
    "U62_GLOBAL_STORAGE_MAX_BYTES": 10485760,
    "U62_GLOBAL_STORAGE_MAX_OBJECTS": 100,
    "U62_GLOBAL_STORAGE_MAX_UPLOADS_PER_DAY": 500,
    "U62_ACCOUNT_STORAGE_MAX_BYTES": 1048576,
    "U62_ACCOUNT_STORAGE_MAX_OBJECTS": 10,
    "U62_ACCOUNT_STORAGE_MAX_UPLOADS_PER_DAY": 50,
}


class CleanupFactoryTests(SimpleTestCase):
    def make(self, **changes):
        configuration = dict(VALID)
        configuration.update(changes)
        return override_settings(**configuration)

    def test_disabled_by_default(self):
        with self.make(U62_CLEANUP_ENABLED=False):
            with self.assertRaises(RuntimeError):
                build_cleanup_dependencies()

    def test_string_cannot_enable_cleanup(self):
        with self.make(U62_CLEANUP_ENABLED="true"):
            with self.assertRaises(RuntimeError):
                build_cleanup_dependencies()

    def test_r2_must_be_enabled(self):
        with self.make(U62_R2_ENABLED=False):
            with self.assertRaises(RuntimeError):
                build_cleanup_dependencies()

    def test_missing_bucket_rejected(self):
        with self.make(U62_R2_BUCKET=None):
            with self.assertRaises(ValueError):
                build_cleanup_dependencies()

    def test_missing_client_factory_rejected(self):
        with self.make(U62_R2_CLIENT_FACTORY=None):
            with self.assertRaises(ValueError):
                build_cleanup_dependencies()

    def test_zero_global_quota_rejected(self):
        with self.make(U62_GLOBAL_STORAGE_MAX_OBJECTS=0):
            with self.assertRaises(ValueError):
                build_cleanup_dependencies()

    def test_boolean_quota_rejected(self):
        with self.make(U62_ACCOUNT_STORAGE_MAX_BYTES=True):
            with self.assertRaises(ValueError):
                build_cleanup_dependencies()

    def test_missing_client_rejected(self):
        with self.make():
            with patch(
                "ai_assistant.tts.cleanup_factory.import_string",
                return_value=lambda: None,
            ):
                with self.assertRaises(RuntimeError):
                    build_cleanup_dependencies()

    def test_injected_client_constructs_dependencies(self):
        fake_client = Mock()

        with self.make():
            with patch(
                "ai_assistant.tts.cleanup_factory.import_string",
                return_value=lambda: fake_client,
            ):
                repository, store = build_cleanup_dependencies()

        self.assertIs(store.client, fake_client)
        self.assertEqual(store.bucket, "isolated-test-bucket")
        self.assertEqual(
            repository.global_limits.max_objects, 100
        )
        self.assertEqual(
            repository.account_limits.max_objects, 10
        )

        fake_client.put_object.assert_not_called()
        fake_client.get_object.assert_not_called()
        fake_client.delete_object.assert_not_called()
