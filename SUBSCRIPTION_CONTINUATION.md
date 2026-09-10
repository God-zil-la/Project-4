# Subscription continuation and scheduled plan changes

Base: 4506f308e1013e861db6fd6836a87686dab8544f.

## Original behavior

UpgradeSubscriptionView replaced the Premium item using always_invoice,
error_if_incomplete, and an unchanged billing anchor, but omitted
cancel_at_period_end=False. Stripe therefore retained the existing cancellation.
The Billing page explicitly described that behavior. There were no resume or
downgrade routes, and reconciliation had no representation of a pending plan
change. Upgrade keys were derived from individual form tokens.

The deployed legacy SEK-to-USD recovery intentionally preserves cancellation.
That behavior remains unchanged; continuing a supported current USD plan is a
separate owner-confirmed operation.

## Result

- Resume clears cancel_at_period_end on the same supported paid monthly plan.
  It changes neither the item nor the billing anchor, and creates no proration.
- Premium to Pro clears cancellation in the same subscription update that
  invoices the prorated difference. error_if_incomplete protects against a
  failed payment applying the upgrade. Renewal remains on the existing boundary.
- Pro to Premium first clears an existing period-end cancellation, then creates
  a schedule from the same subscription. The first phase retains the current
  Pro price through its existing end timestamp. The second phase uses Premium
  for one monthly iteration, then releases the schedule with Premium continuing
  normally. Both schedule update and phase proration behaviors are none.
- No operation creates a replacement subscription or checkout.

The downgrade needs separate Stripe calls. If continuation succeeds and later
scheduling fails, Pro may already renew normally while the downgrade remains
unconfirmed. Billing explicitly reports this and exposes Retry saved change.
There is no automatic compensating cancellation, which could discard subsequent
owner intent. Retries stop before Stripe's 24-hour idempotency retention boundary
(the application limit is 23 hours); unresolved older intents require support.

## Persistence and reconciliation

Migration ai_payments.0005_subscriptionchange adds SubscriptionChange, one row
per profile, storing the action, UUID retry identity, source subscription/item/
price/period, fixed scheduling parameters, provider schedule and target price
identifiers, start time, and confirmation status. No UserProfile fields or
entitlement rules are replaced. There is no data migration or automatic account
change.

The profile row lock serializes local actions and webhooks. Consent is committed
before writes to Stripe. Provider exceptions retain the intent and completed
stages; retries use the same provider keys and parameters. A definitive upgrade
CardError allows a fresh owner-confirmed attempt after payment correction because
Stripe caches the failed response. Network uncertainty never rotates that key.

Reconciliation reads the current Stripe subscription and, for a tracked
configured downgrade, its schedule. It verifies ownership, mode, attachment,
target price, phase boundary, release behavior, and cancellation conflicts.
Only a confirmed schedule is shown as a pending downgrade. Actual subscription
prices and status continue to determine access; neither saved intent nor plan
metadata grants Premium or Pro. Terminal subscriptions remove pending display;
failed payment removes paid access through the existing rules.

The existing customer subscription and invoice handlers remain in place. Schedule
updated/released/completed/canceled/aborted events now reconcile the tracked
schedule using fresh provider state. Schedule events do not send payment emails.
Existing invoice receipt and cancellation email processing is unchanged.

## Guardrails and user experience

Forms are authenticated, POST-only, CSRF-protected, private, and signed for the
owner, action, subscription, current plan, period boundary, and cancellation
state. Fresh provider state is checked before a mutation. The server ignores
client-supplied prices and customer IDs.

Mutations fail closed for multiple nonterminal subscriptions, mismatched owners
or modes, open checkout sessions, unresolved checkout/recovery intents, open,
draft or uncollectible invoices, pending invoice items, paused or scheduled
subscriptions not belonging to this change, unpaid latest invoices, pending
updates, custom cancellation dates, unsupported price/item structures, and
custom discount/tax/transfer settings. A new conflicting operation cannot replace
an unconfirmed or scheduled one. A saved change also blocks duplicate checkout.

Billing shows the current entitlement, cancellation and access end date, renewal
date, pending Premium downgrade and effective date, or an explicit unconfirmed /
conflicting state. Eligible users see Resume subscription, Upgrade to Pro, or
Schedule downgrade to Premium. An interrupted operation gets Retry saved change.
Payment failures direct users to Manage subscription and a new upgrade form.

Removing a confirmed downgrade, canceling instead, or resolving external schedule
edits requires support; this release does not add an automatic schedule-release
button. Support should inspect Stripe, release or correct the schedule according
to confirmed owner intent, and refresh Billing. It must not delete an unresolved
local intent simply to allow another mutation. If cancellation and downgrade
coexist, the application reports the conflict and does not silently clear either.

## Validation

Python 3.13, Django 5.2.17, Stripe SDK 12.2.0 (the repository's pinned versions).
207 tests passed: 177 existing tests plus 30 new continuation regressions.
The 25 existing subscription-management tests were updated for the new consent
forms, provider preflight calls, and intentional cancellation behavior.
157 billing tests and 50 other project tests pass, including all existing legacy
recovery and transactional-email regressions.

Run from the repository with its installed dependencies:

    python run_local_regressions.py
    python manage.py makemigrations --check --dry-run --settings=ai_assistant.buildabot.test_settings

The runner uses an in-memory database, placeholder credentials, in-memory email
and cache settings, and blocks socket connections. Expected error logs exercise
failure paths; the final result is OK. Changed Python files pass Ruff. Migration
checks report no missing changes. Both billing templates remain identical.

These are mocked provider regressions, including actual Stripe SDK object shapes.
They do not prove live provider execution or PostgreSQL concurrent-worker behavior.
No live Stripe calls, Heroku changes, commits, pushes, or deployments were made.
The original Desktop checkout remains clean at the base commit.

## Eventual production steps (not performed)

1. Review and apply the patch to the exact base, then use the normal approved
   release process. Apply migration 0005 before serving code that queries the new
   model, using the project's normal migration/release procedure.
2. Keep existing webhook events and add subscription_schedule.updated,
   subscription_schedule.released, subscription_schedule.completed,
   subscription_schedule.canceled, and subscription_schedule.aborted to the
   endpoint if it uses an explicit event allowlist. Ensure any restricted Stripe
   key permits schedule and price operations and the invoice/session reads.
3. Validate the flow in a separate Stripe sandbox/Test Mode account, including a
   renewal boundary, declined payment, lost-response retry, schedule release, and
   receipt behavior. Review concurrency with the production database engine.
4. Refresh Billing. Existing Pro access, renewal and cancellation are untouched
   by deployment. The existing canceled Pro subscription only resumes if its owner
   explicitly submits Resume or the downgrade continuation form.
5. No manual price creation, background downgrade job, environment variable,
   automatic entitlement backfill, or legacy recovery rerun is required. Products
   and prices needed for a change are created idempotently on owner confirmation.

## Provider references

- https://docs.stripe.com/api/subscription_schedules/create?api-version=2025-04-30.basil
  (from_subscription requires separate creation and configuration calls).
- https://docs.stripe.com/api/subscription_schedules/update?api-version=2025-04-30.basil
  (phases, proration behavior, and release semantics).
- https://docs.stripe.com/api/subscriptions/update?api-version=2025-04-30.basil
  (cancel_at_period_end and payment_behavior).

The installed 12.2.0 SDK's SubscriptionSchedule parameter types were also inspected
for phases, price_data, and iterations compatibility.
