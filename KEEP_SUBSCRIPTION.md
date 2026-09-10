# Keep the current subscription

Keep Pro releases only the tracked, configured Pro-to-Premium schedule after
fresh owner, mode, attachment, phase, current price, period and payment checks.
The authenticated signed POST commits consent under the profile lock before
provider execution. It retains the schedule identity and uses a distinct stable
release key. Uncertain writes remain retryable for 23 hours. A released schedule
must identify the same subscription with unchanged Pro terms before success.
Schedule cancellation is never used. No subscription or Checkout is created.

Canceled Pro and Premium use the existing resume operation with Keep Pro and
Keep Premium labels. Premium-to-Pro upgrades apply immediately with payment
protection; there is no pending upgrade reversal. Existing proration guards and
Stripe price/status entitlement authority are unchanged. No migration is needed.

Validation uses mocked Stripe calls and an in-memory database with network
connections blocked. Live provider behavior and PostgreSQL concurrent workers
are not exercised. Stripe cannot atomically compare a schedule and release it;
external edits can race provider reads. Cancellation is preserved on release,
and fresh reconciliation checks the resulting subscription before confirmation.
Unsafe or conflicting states require support. Nothing is deployed automatically.
