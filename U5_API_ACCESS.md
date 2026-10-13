# U5 API Access — local release candidate, not deployed

Scope follows README's “Planned U5 API Access”: account key management and
rotation, assistant invocation, plan/ownership validation, shared usage/rate
limits, request validation, documentation and Discord integration.

## Account key management

Sign in and open **API Access** in the navigation (`/accounts/api-access/`).
Pro, including currently effective complimentary Pro, can create/rotate a key.
The replacement is displayed only in the POST response. Save it securely then.
GET never displays a stored key. Rotation invalidates the previous key.
Revocation remains available after downgrade. Management requires a signed-in
browser session and CSRF protection. Native, customer and Discord tokens cannot
replace this browser session.

One account key invokes that account's assistants. This does not add assistant
CRUD, multiple named keys, per-key billing, or new plan requirements.
Customer keys are stored only as SHA-256 digests of high-entropy random secrets.
Keep keys on your server, never in public/browser/mobile code or query strings.

## Invoke an assistant

Use the intended backend's HTTPS origin. Example shell variables below must be
set securely in your own server environment; the example contains no real key.

```sh
curl --request POST "$U5_BACKEND/accounts/api/public-chat/" \
  --header "X-API-KEY: $U5_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '{"bot_id":123,"message":"Hello"}'
```

`bot_id` identifies an assistant you own (visible in its Discord Setup page).
The body must be an object; `message` is nonempty text. Optional
`conversation_id` is a conversation UUID belonging to your account and that
assistant. Without it, a new conversation starts; private/latest web history is
not implicitly reused. A continuation uses the same endpoint and headers:

```json
{"bot_id":123,"message":"Tell me more","conversation_id":"<returned UUID>"}
```

Success (200) includes `response`, `conversation_id`, `plan`, token/usage fields
and domain information from the shared chat service. Domain refusals are normal
responses and follow existing usage accounting. Knowledge, monthly quotas and
rate limits use the existing backend pipeline. Current Pro limits documented
in the project are 10,000 messages/month and 120 requests/minute, account-wide.
Plan changes do not reset usage. A disconnected client or timeout does not prove
that an AI request was cancelled. There is no automatic retry or idempotency
guarantee; avoid automatically resending chat requests.

| Status | Meaning |
|---|---|
| 400 | Invalid request/conversation, or a shared chat-service validation error |
| 401 | Missing, invalid, revoked key or inactive/deleted account |
| 403 | Pro entitlement or monthly usage restriction |
| 404 | Assistant unavailable or owned by another account |
| 429 | Rate limit; wait `retry_after_seconds` from the JSON response |
| 500 | Sanitized processing failure |

Keys and chat responses are marked `no-store`. The API key has no authority on
native login endpoints or the Discord route. Signing into the browser does not
replace `X-API-KEY` for customer chat.

## Discord boundary

Discord Setup generates a separate `Discord dsc_…` credential bound to the
account and assistant. Its digest is stored in `DiscordIntegration`; revocation
is independent from the customer key and native login token. Current Pro and
active ownership are checked on each request. Discord conversations are bound
to that integration; another integration's or a private web conversation UUID
is rejected. Existing unbound Discord histories start fresh after this change.

Read `ai_assistant/static/discord_bridge/README.txt` for current bridge setup,
permissions, trigger commands and privacy boundaries. Older PDF guides are
retained as historical help and are explicitly labelled as potentially stale.

## Migration and release

`accounts.0012` expands the existing key field and hashes existing customer
keys. Existing clients keep using their original secret; do not send a digest.
Newly created accounts store an undisclosed digest until an owner creates a key.
`bots.0025` is the preceding Discord credential migration; `bots.0026` adds the
conversation binding. User, assistant and conversation data are retained.

Coordinate migration and application rollout: old code cannot authenticate
against the new digests. A rollback of `accounts.0012` **invalidates all customer
API keys** by replacing them with undisclosed random values compatible with the
old field. It cannot recover plaintext. Returning to U5 requires customers to
create new keys. Do not simply roll old application code onto the new schema.
Prepare the usual database backup and agree a maintenance/rollback procedure
before any approved deployment. No migration has been run on production.

Local SQLite tests do not verify PostgreSQL migrations, multi-worker Redis,
TLS/proxy configuration, actual Heroku values, or the Discord gateway.
Real Discord E2E and live domain tests remain release gates until test-only
credentials, a confirmed test server and an isolated reachable backend exist.
