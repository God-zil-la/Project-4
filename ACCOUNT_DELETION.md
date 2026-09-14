# AI Assistant account deletion

Status: implementation for review; no deployment or production data changes.

## Entry points

- `/delete-account/`: public instructions and support email; no login or installation needed.
- Dashboard → Account settings → Delete my account and data → `/accounts/delete/`.
- Online confirmation requires the current password, a checked confirmation and a CSRF-protected POST. GET never deletes. Only the authenticated user's ID is used.
- The public email route is a manual support request, not an automatic email-driven deletion endpoint. Verify account ownership before acting; never treat knowledge of an email address as proof.

## Data audit and implementation

The account service locks the user and profile and deletes inside a database transaction. It removes KnowledgeBase rows both for owned bots and for `uploaded_by`, whose existing `SET_NULL` relation otherwise preserves uploads. User cascades remove UserProfile, REST tokens, Bot, Conversation, ChatMessage (including legacy rows without a conversation), both BotUsageLog models, CheckoutAttempt, SubscriptionChange and SubscriptionRecovery. BotTemplate is global, not user-owned, and remains.

BillingEmail has no user foreign key. Local copies addressed to the account's current email are explicitly removed case-insensitively. Historical addresses and ambiguous legacy attribution require support review; there is no email-history model. Already-sending/delivered email cannot be recalled by deleting an outbox row.

KnowledgeBase post-delete signals persist FileDeletionJob in the same transaction. Only after commit does cleanup call the field's configured storage backend. Failures preserve the job for retry, without storing raw provider errors. Rollback preserves both the database content and the original file. A file referenced by another KnowledgeBase row is not removed until the final reference is deleted. This also covers ordinary bot cascades and individual Knowledge Base deletion. Existing orphaned files created before this feature cannot be attributed automatically and need a separate inventory review.

Sessions use signed cookies. Removing the user invalidates authentication from old cookies; logout clears the current browser session. Removing the profile/API token invalidates new API/Discord requests. Other-device cookies and local Discord bridge configuration are not remotely erased. A request already sent to a provider cannot be recalled.

## Billing safety

The flow makes read-only Stripe checks. It does not cancel subscriptions, issue refunds, delete Stripe customers or change provider billing. It checks all pages of subscriptions, checkout sessions and subscription schedules, plus local pending recovery/change/checkout state. Unknown or active state blocks automatic deletion and provides a support path. Cancel-at-period-end is still active; support can resolve earlier termination with the user and rerun the deletion flow. Completed local billing records are deleted after those checks pass. Provider invoices/customer records require provider and legal review.

No Google Play purchase model, verification or cancellation integration exists in this Django version. Before enabling Google Play Billing, extend this guard to cover its real purchase/entitlement state and verify the Android app exposes the dashboard deletion option or links directly to `/delete-account/`.

## Support operations

Apply the included migration through the normal release process before serving the changed code. No migration has been applied to the user's live database by this task.

For an ownership-verified email request, resolve billing, identify the exact user ID, then use:

```text
python manage.py delete_ai_account --user-id USER_ID --confirm-email ACCOUNT_EMAIL --ownership-verified
```

Use this command or the authenticated flow for account erasure. A User pre-delete signal also enforces billing checks and extra upload/outbox/provider-follow-up work for Django ORM and admin deletion, so these paths cannot silently skip cleanup. Raw SQL bypasses Django signals and must not be used for account erasure.

The service creates a DeletionFollowUp record with only email, Stripe customer ID if any, and request date. Staff can inspect pending follow-ups and file jobs in Django admin. Coordinate erasure with the configured AI, email, hosting/storage and payment providers using their actual account agreements and controls; review support correspondence and any retained billing/security data; notify the requester of completion or the precise retention exception. Then purge the follow-up contact data:

```text
python manage.py complete_deletion_followup --id FOLLOWUP_ID --provider-review-complete
```

Run and monitor the storage retry command regularly and after storage incidents:

```text
python manage.py retry_file_deletions
```

It exits unsuccessfully when cleanup still fails. No production scheduler has been created. Failed jobs and follow-up records have no automatic time-based purge because purging them would lose unfinished work. Successful jobs are removed.

## Retention decisions required before release

- Assign an owner for support@myaiassistantapp.se, identity verification, provider follow-ups, and completion notices. Set a response/completion target and a schedule/alert for storage retries.
- Confirm actual hosting log, backup, mailbox and provider retention rules, and any legal billing/security exceptions. None is configured in this repository. Do not claim specific periods until verified.
- StripeEvent retains only event IDs and processing timestamps indefinitely in this implementation for webhook deduplication; decide a justified retention period if one is required and implement it before promising one.
- The existing `ai-rate-limit:USER_ID` counter has a 60-second TTL. Cleanup attempts to remove it immediately; expiry remains the fallback.
- Confirm the released Android build exposes the deletion path, and set the public deletion URL in Play Console after publication. Native Android code was not part of this Django change.

The public pages disclose current behavior and unresolved external retention instead of making unsupported promises. This change alone does not certify the release or third-party operations as compliant.
