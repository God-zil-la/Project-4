from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from django.core.exceptions import ImproperlyConfigured
from ai_assistant.buildabot.cache_config import build_cache_config
from ai_assistant.bots.chat_service import _check_rate_limit, ChatRateLimitError, ChatServiceError
from ai_assistant.bots.checks import production_cache_check

class RedisTests(SimpleTestCase):
    def test_configuration(self):
        self.assertIn('LocMem', build_cache_config('')['default']['BACKEND'])
        options = build_cache_config('rediss://localhost:6379/0')['default']['OPTIONS']
        self.assertFalse(options['IGNORE_EXCEPTIONS'])
        self.assertEqual(options['CONNECTION_POOL_KWARGS']['ssl_cert_reqs'], 'required')
        for url in ['https://localhost', 'redis://', 'rediss://localhost?ssl_cert_reqs=none']:
            with self.assertRaises(ImproperlyConfigured):
                build_cache_config(url)

    @override_settings(DEBUG=False)
    def test_production_rejects_local_cache(self):
        self.assertEqual(production_cache_check(None)[0].id, 'bots.E001')

    @patch('ai_assistant.bots.chat_service.cache')
    def test_rate_limit_and_expiry_race(self, cache):
        user, profile = SimpleNamespace(pk=1), SimpleNamespace(plan='free')
        cache.add.return_value = False
        cache.incr.side_effect = [ValueError(), 21]
        with self.assertRaises(ChatRateLimitError):
            _check_rate_limit(user, profile)
        cache.set.assert_not_called()
        self.assertEqual(cache.add.call_count, 2)

    @patch('ai_assistant.bots.chat_service.cache')
    def test_failure_is_closed_and_sanitized(self, cache):
        cache.add.side_effect = RuntimeError('redis://secret@host')
        with self.assertRaisesMessage(ChatServiceError, 'AI service is temporarily unavailable.'):
            _check_rate_limit(SimpleNamespace(pk=1), SimpleNamespace(plan='free'))
