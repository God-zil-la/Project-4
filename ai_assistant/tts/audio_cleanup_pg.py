"""Isolated PostgreSQL cleanup repository.

Requires separately reviewed PostgreSQL tables.
No database connection is opened at import.
This module does not start workers or activate R2.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from django.db import connection, transaction

from .audio_cleanup import CleanupJob
from .audio_storage import MAX_AUDIO_BYTES


@dataclass(frozen=True)
class StorageLimits:
    max_bytes: int
    max_objects: int
    max_uploads_per_day: int

    def __post_init__(self):
        if any(
            type(value) is not int or value <= 0
            for value in (
                self.max_bytes,
                self.max_objects,
                self.max_uploads_per_day,
            )
        ):
            raise ValueError("invalid_storage_limits")


class StorageQuotaExceeded(Exception):
    pass


def _require_postgres():
    if connection.vendor != "postgresql":
        raise RuntimeError("postgresql_required")


def _validate_request(request_id, account_id, size_bytes, expires_at):
    if not isinstance(request_id, UUID):
        raise ValueError("invalid_request_id")
    if type(account_id) is not int or account_id <= 0:
        raise ValueError("invalid_account_id")
    if type(size_bytes) is not int or not 1 <= size_bytes <= MAX_AUDIO_BYTES:
        raise ValueError("invalid_audio_size")
    if not isinstance(expires_at, datetime) or (
        expires_at.tzinfo is None or
        expires_at.utcoffset() is None
    ):
        raise ValueError("invalid_expiry")


class PostgresAudioRepository:
    def __init__(self, *, global_limits, account_limits):
        if not isinstance(global_limits, StorageLimits):
            raise ValueError("global_limits_required")
        if not isinstance(account_limits, StorageLimits):
            raise ValueError("account_limits_required")
        self.global_limits = global_limits
        self.account_limits = account_limits

    @staticmethod
    def _scopes(account_id):
        return ("global", f"account:{account_id}")

    @staticmethod
    def _prepare_budgets(cursor, scopes, today):
        for scope in scopes:
            cursor.execute(
                "INSERT INTO tts_audio_budget (scope) VALUES (%s) "
                "ON CONFLICT (scope) DO NOTHING",
                [scope],
            )

        budgets = {}
        for scope in scopes:
            cursor.execute(
                "SELECT bytes_reserved, objects_reserved, "
                "uploads_today, usage_day "
                "FROM tts_audio_budget WHERE scope = %s "
                "FOR UPDATE",
                [scope],
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("budget_missing")
            used_bytes, objects, uploads, usage_day = row
            if usage_day != today:
                cursor.execute(
                    "UPDATE tts_audio_budget "
                    "SET uploads_today = 0, usage_day = %s "
                    "WHERE scope = %s",
                    [today, scope],
                )
                uploads = 0
            budgets[scope] = (used_bytes, objects, uploads)
        return budgets

    def reserve(self, *, request_id, account_id, size_bytes, expires_at):
        """Reserve capacity and record cleanup BEFORE external upload.

        Returns True for a new reservation, False for exact replay.
        An existing reservation never extends expiry or consumes quota twice.
        """
        _validate_request(request_id, account_id, size_bytes, expires_at)
        _require_postgres()
        now = datetime.now(timezone.utc)
        if not now < expires_at <= now + timedelta(minutes=16):
            raise ValueError("expiry_out_of_range")

        scopes = self._scopes(account_id)
        limits = (self.global_limits, self.account_limits)

        with transaction.atomic():
            with connection.cursor() as cursor:
                budgets = self._prepare_budgets(cursor, scopes, now.date())

                cursor.execute(
                    "SELECT account_id, size_bytes, expires_at "
                    "FROM tts_audio_cleanup "
                    "WHERE request_id = %s",
                    [str(request_id)],
                )
                existing = cursor.fetchone()
                if existing is not None:
                    owner, size, expiry = existing
                    if (
                        owner != account_id or
                        size != size_bytes or
                        expiry != expires_at
                    ):
                        raise ValueError("reservation_conflict")
                    return False

                for scope, bound in zip(scopes, limits):
                    used_bytes, objects, uploads = budgets[scope]
                    if (
                        used_bytes + size_bytes > bound.max_bytes or
                        objects + 1 > bound.max_objects or
                        uploads + 1 > bound.max_uploads_per_day
                    ):
                        raise StorageQuotaExceeded("audio_storage_quota")

                cursor.execute(
                    "INSERT INTO tts_audio_cleanup "
                    "(request_id, account_id, size_bytes, "
                    "expires_at, next_attempt_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [
                        str(request_id), account_id, size_bytes,
                        expires_at, expires_at,
                    ],
                )

                for scope in scopes:
                    cursor.execute(
                        "UPDATE tts_audio_budget "
                        "SET bytes_reserved = bytes_reserved + %s, "
                        "objects_reserved = objects_reserved + 1, "
                        "uploads_today = uploads_today + 1 "
                        "WHERE scope = %s",
                        [size_bytes, scope],
                    )
        return True

    def claim_due(self, *, now, limit, lease_duration):
        _require_postgres()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("timezone_required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid_batch_limit")
        if not isinstance(lease_duration, timedelta) or (
            lease_duration.total_seconds() <= 0
        ):
            raise ValueError("invalid_lease_duration")

        result = []
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT request_id, expires_at "
                    "FROM tts_audio_cleanup "
                    "WHERE next_attempt_at <= %s "
                    "AND (lease_until IS NULL OR lease_until <= %s) "
                    "ORDER BY next_attempt_at, request_id "
                    "FOR UPDATE SKIP LOCKED LIMIT %s",
                    [now, now, limit],
                )
                rows = cursor.fetchall()

                for request_id, expires_at in rows:
                    token = uuid4()
                    cursor.execute(
                        "UPDATE tts_audio_cleanup "
                        "SET lease_token = %s, lease_until = %s "
                        "WHERE request_id = %s",
                        [
                            str(token), now + lease_duration,
                            str(request_id),
                        ],
                    )
                    result.append(
                        (CleanupJob(request_id, expires_at), token)
                    )
        return result

    def acknowledge(self, *, job, lease):
        """Release quotas only for an owned completed deletion."""
        _require_postgres()
        if not isinstance(lease, UUID):
            raise ValueError("invalid_lease")

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Discover account before taking budget locks.
                cursor.execute(
                    "SELECT account_id FROM tts_audio_cleanup "
                    "WHERE request_id = %s",
                    [str(job.request_id)],
                )
                found = cursor.fetchone()
                if found is None:
                    return False

                scopes = self._scopes(found[0])
                self._prepare_budgets(
                    cursor, scopes, datetime.now(timezone.utc).date()
                )

                cursor.execute(
                    "SELECT account_id, size_bytes "
                    "FROM tts_audio_cleanup "
                    "WHERE request_id = %s AND lease_token = %s "
                    "FOR UPDATE",
                    [str(job.request_id), str(lease)],
                )
                row = cursor.fetchone()
                if row is None:
                    return False

                account_id, size_bytes = row
                if account_id != found[0]:
                    return False

                cursor.execute(
                    "DELETE FROM tts_audio_cleanup "
                    "WHERE request_id = %s AND lease_token = %s",
                    [str(job.request_id), str(lease)],
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("cleanup_ack_conflict")

                for scope in scopes:
                    cursor.execute(
                        "UPDATE tts_audio_budget "
                        "SET bytes_reserved = bytes_reserved - %s, "
                        "objects_reserved = objects_reserved - 1 "
                        "WHERE scope = %s "
                        "AND bytes_reserved >= %s "
                        "AND objects_reserved >= 1",
                        [size_bytes, scope, size_bytes],
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError("budget_accounting_conflict")
        return True

    def retry(self, *, job, lease, retry_at):
        _require_postgres()
        if not isinstance(lease, UUID):
            raise ValueError("invalid_lease")
        if retry_at.tzinfo is None or retry_at.utcoffset() is None:
            raise ValueError("timezone_required")

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE tts_audio_cleanup "
                    "SET lease_token = NULL, lease_until = NULL, "
                    "next_attempt_at = %s, "
                    "retry_count = retry_count + 1 "
                    "WHERE request_id = %s AND lease_token = %s",
                    [retry_at, str(job.request_id), str(lease)],
                )
                return cursor.rowcount == 1
