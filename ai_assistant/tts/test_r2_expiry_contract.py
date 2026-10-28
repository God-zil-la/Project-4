"""R2 conditional write and immutable deadline contracts, fake client only."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from django.test import SimpleTestCase

from .r2_audio_store import R2AudioStore


class R2ExpiryContractTests(SimpleTestCase):
    def setUp(self):
        self.client = Mock()
        self.store = R2AudioStore(client=self.client, bucket='fake-private')
        self.id = uuid4()
        self.expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

    def test_deadline_passed_to_metadata(self):
        self.store.save(request_id=self.id, audio=b'abc', expires_at=self.expiry)
        self.assertEqual(
            self.client.put_object.call_args.kwargs['Metadata']['expires-at'],
            str(int(self.expiry.timestamp())),
        )

    def test_expired_deadline_rejected_before_put(self):
        try:
            self.store.save(request_id=self.id, audio=b'abc',
                            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        except ValueError:
            pass
        else:
            self.fail('Expected expired deadline to fail')
        self.client.put_object.assert_not_called()

    def test_precondition_conflict_must_verify_identical_bytes(self):
        conflict = RuntimeError('precondition')
        conflict.response = {'Error': {'Code': 'PreconditionFailed'}}
        self.client.put_object.side_effect = conflict
        self.client.get_object.return_value = {
            'Metadata': {'expires-at': str(int(self.expiry.timestamp()))},
            'ContentLength': 3, 'Body': BytesIO(b'xyz'),
        }
        with self.assertRaisesRegex(ValueError, 'existing_audio_conflict'):
            self.store.save(request_id=self.id, audio=b'abc', expires_at=self.expiry)

    def test_precondition_conflict_accepts_only_same_bytes_and_expiry(self):
        conflict = RuntimeError('precondition')
        conflict.response = {'Error': {'Code': 'PreconditionFailed'}}
        self.client.put_object.side_effect = conflict
        self.client.get_object.return_value = {
            'Metadata': {'expires-at': str(int(self.expiry.timestamp()))},
            'ContentLength': 3, 'Body': BytesIO(b'abc'),
        }
        self.store.save(request_id=self.id, audio=b'abc', expires_at=self.expiry)

    def test_different_metadata_expiry_is_not_accepted(self):
        self.client.get_object.return_value = {
            'Metadata': {'expires-at': str(int(self.expiry.timestamp()) + 60)},
            'ContentLength': 3, 'Body': BytesIO(b'abc'),
        }
        self.assertIsNone(self.store.load(request_id=self.id, expected_expiry=self.expiry))
