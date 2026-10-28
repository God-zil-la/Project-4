"""Offline-only tests: no R2 connections and no credentials used."""
import sys
from types import ModuleType
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from .r2_client_factory import build_r2_client


EXAMPLE_ENDPOINT = "https://" + "a" * 32 + ".r2.cloudflarestorage.com"


class R2ClientFactoryTests(SimpleTestCase):
    @override_settings(U62_R2_ENABLED=False)
    def test_disabled_fails_before_client_import(self):
        with self.assertRaisesRegex(RuntimeError, "r2_disabled"):
            build_r2_client()

    @override_settings(U62_R2_ENABLED=True, U62_R2_ENDPOINT_URL="http://example.com",
                       U62_R2_ACCESS_KEY_ID="placeholder", U62_R2_SECRET_ACCESS_KEY="placeholder")
    def test_non_r2_or_insecure_endpoint_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_r2_endpoint"):
            build_r2_client()

    @override_settings(U62_R2_ENABLED=True, U62_R2_ENDPOINT_URL=EXAMPLE_ENDPOINT,
                       U62_R2_ACCESS_KEY_ID="", U62_R2_SECRET_ACCESS_KEY="placeholder")
    def test_missing_access_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing_r2_access_key"):
            build_r2_client()

    @override_settings(U62_R2_ENABLED=True, U62_R2_ENDPOINT_URL=EXAMPLE_ENDPOINT,
                       U62_R2_ACCESS_KEY_ID="placeholder", U62_R2_SECRET_ACCESS_KEY="")
    def test_missing_secret_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing_r2_secret_key"):
            build_r2_client()

    @override_settings(U62_R2_ENABLED=True, U62_R2_ENDPOINT_URL=EXAMPLE_ENDPOINT,
                       U62_R2_ACCESS_KEY_ID="placeholder", U62_R2_SECRET_ACCESS_KEY="placeholder")
    def test_client_created_only_by_explicit_invocation(self):
        fake_boto3 = ModuleType("boto3")
        fake_boto3.client = Mock(return_value=object())
        fake_botocore = ModuleType("botocore")
        fake_config = ModuleType("botocore.config")
        fake_config.Config = Mock(return_value=object())
        fake_botocore.config = fake_config
        with patch.dict(sys.modules, {"boto3": fake_boto3, "botocore": fake_botocore,
                                      "botocore.config": fake_config}):
            client = build_r2_client()
        self.assertIsNotNone(client)
        fake_boto3.client.assert_called_once()
        kwargs = fake_boto3.client.call_args.kwargs
        self.assertEqual(kwargs["endpoint_url"], EXAMPLE_ENDPOINT)
        self.assertEqual(kwargs["region_name"], "auto")
        self.assertEqual(kwargs["aws_access_key_id"], "placeholder")
        self.assertEqual(kwargs["aws_secret_access_key"], "placeholder")
