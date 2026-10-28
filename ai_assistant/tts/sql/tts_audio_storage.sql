-- U6.2 isolated PostgreSQL design.
-- REVIEW ONLY. DO NOT APPLY TO PRODUCTION.

CREATE TABLE tts_audio_cleanup (
    request_id UUID PRIMARY KEY,
    account_id BIGINT NOT NULL,
    size_bytes BIGINT NOT NULL
        CHECK (size_bytes BETWEEN 1 AND 8388608),
    expires_at TIMESTAMPTZ NOT NULL,
    next_attempt_at TIMESTAMPTZ NOT NULL,
    lease_token UUID,
    lease_until TIMESTAMPTZ,
    retry_count INTEGER NOT NULL DEFAULT 0
        CHECK (retry_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (lease_token IS NULL AND lease_until IS NULL)
        OR
        (lease_token IS NOT NULL AND lease_until IS NOT NULL)
    )
);

CREATE INDEX tts_audio_cleanup_due_idx
    ON tts_audio_cleanup (next_attempt_at, lease_until);

CREATE TABLE tts_audio_budget (
    scope TEXT PRIMARY KEY,
    bytes_reserved BIGINT NOT NULL DEFAULT 0
        CHECK (bytes_reserved >= 0),
    objects_reserved INTEGER NOT NULL DEFAULT 0
        CHECK (objects_reserved >= 0),
    uploads_today INTEGER NOT NULL DEFAULT 0
        CHECK (uploads_today >= 0),
    usage_day DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Intended reservation transaction:
-- 1. Lock global and account budget rows in a consistent order.
-- 2. Check quotas and existing request_id.
-- 3. Reserve bytes and operations atomically.
-- 4. Insert cleanup job before uploading to R2.
-- 5. Commit reservation before external storage I/O.
--
-- Intended cleanup transaction:
-- 1. Claim due jobs with FOR UPDATE SKIP LOCKED.
-- 2. Commit short-lived leases.
-- 3. Delete objects from R2 outside the DB transaction.
-- 4. Acknowledge only with the matching lease token.
-- 5. Release reserved bytes only after acknowledged deletion.
-- 6. Retry failed and uncertain deletions.
--
-- IMPORTANT:
-- This schema is not a complete implementation.
-- Reservation, leasing, quota enforcement and crash recovery
-- must be implemented and tested before deployment.
