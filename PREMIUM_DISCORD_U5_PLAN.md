# Premium Discord addition — U5 joint release

Status: development only. No production deployment, merge, migration or release authorized.

## Release boundary
- Base: backend `release/u5-u4-pricing-20261013`, mobile `release/mobile-u4-u5-20261013`.
- Ship with the pending U4/U5 release after iOS launch and explicit owner approval.
- U6 remains a separate Work development and later release (target January 2027).
- Preserve existing Pro Discord, customer API, subscriptions, Stripe, Play Billing, IAP, and Free plan.

## Premium entitlement
- Up to **three active Discord guilds per Premium account**, not per assistant.
- Shared Premium usage limit: **3,000 messages/month** across web, mobile and all linked Discord guilds; existing cost/rate limits also apply.
- Guild members can use **generic AI only**. No customer Bot object, private prompts, knowledge chunks, assistant-specific conversation history, or customer API access.
- A removed guild frees a slot. Guild ownership must be verified with Discord OAuth2/install callbacks or a comparably secure guild authorization proof; never trust a submitted guild ID alone.
- Premium downgrade/expiry blocks usage immediately. Pro retains its U5 implementation unchanged.

## Proposed isolated implementation
1. New `premium_discord` Django app (models, services, auth, routes, admin, tests) or isolated module with explicit owner approval if integration requires touching shared routing.
2. Store guild ID unique, account owner, installed/active/revoked timestamps; enforce max three active guilds transactionally and account-wide.
3. A centrally operated Discord bot receives guild/channel/user identifiers. Verify Discord events at ingress, map guild to active Premium owner, and rate-limit to prevent public server abuse.
4. Generic conversation scope is per guild/channel/user or explicitly selected thread. Never call a customer-specific `Bot` or retrieval pipeline. Use a generic service that safely shares existing quota reservation, token/cost accounting, moderation, and model configuration.
5. New Premium-only web/mobile management surfaces for connect, list, disconnect. Preserve Pro screens and flows.
6. Isolate credentials from U5 `DiscordIntegrationAuthentication` and Pro API keys. No secrets in logs or client-readable status responses.

## Release gates (not yet passed)
- Verify new code via backend and mobile test suites; prove Pro U5 and existing billing tests still pass.
- Test simultaneous fourth-guild installation, forged guild ID, downgrade, quota exhaustion, guild removal/reinstall, concurrency, revocation, malformed payloads, and private data non-disclosure.
- Verify real Discord install and message flows, production domain configuration, secret management, rollback and database migration plans in an approved staging environment.
- Owner approval required before any merge, push to release branch, deployment or store submission.

## Open technical detail
A generic AI response path must be separated from `process_bot_message(user, bot, ...)`, which deliberately reads a customer Bot and its Knowledge Base. Do not reuse that method for Premium generic responses.
