# Premium Discord – VS Code handoff (15 October 2026)

Branch: feature/u5-premium-discord-20261015
Base: release/u5-u4-pricing-20261013
Mobile branch: feature/u5-premium-discord-20261015

## Locked scope
Premium: generic Discord bot, maximum 3 connected servers, 3,000 account-wide monthly messages shared with web/mobile. No Premium access to personalized bots, KB, Pro Discord or API. Pro U5 unchanged. No deploy, merge, production DB access, billing edits or release without explicit owner approval. U6 belongs to a different workflow.

## Implemented on branch (not validated)
Premium policy and guild model/service; OAuth, bot installation checks, signed interaction endpoint, general AI; shared message reservation; isolated token usage model and integration into account cost calculation; encrypted database queue, worker command and migrations 0027–0029; plan copy on backend and mobile.

## Mandatory fixes before merge
1. Worker: call expire_stale_interactions() from premium_discord_queue in run_worker loop. Verify that expiry and completion cannot race; add tests for expired jobs, duplicate interactions, worker crashes, queue restarts and multiple workers. A stuck processing job currently cannot recover before its 15-minute token expiry. Ensure exactly-once AI charging and avoid duplicate followups.
2. Heroku process: dedicated worker command exists but Procfile has no Premium worker entry. Do not modify live Procfile/release without approval. Ensure migration chain and runtime worker provisioning are explicitly planned.
3. Security: verify OAuth callback and guild session allowlist; Discord bot membership, CSRF, permissions, bot scope, guild ownership changes, and plan downgrade. Validate command application_id against configured application ID; verify actual Discord command registration and responses.
4. Cost: PremiumDiscordUsageLog is new and included in dashboard/cost_utils.py. Test exact pricing, shared limits, failed OpenAI calls and usage log errors. Important: API calls that succeed but logging fails can still incur cost.
5. UI: implement Premium guild connect/list/disconnect in web and mobile with mobile authentication/deep link compatibility. No fabricated product screens.
6. Tests: run Django system checks, makemigrations --check --dry-run, migration checks, isolated tests, and regression tests for U1–U5. Tests have NOT been run by ChatGPT.
7. Review imported model registration: bots/models.py imports PremiumDiscordGuild only; PremiumDiscordUsageLog and PremiumDiscordJob must also be registered by Django model discovery (import them in bots/models.py).
8. Discord slash command /ask with string option named question must be registered in Discord application. Worker followup is currently non-ephemeral; consider privacy and avoid mentioning Discord users automatically.
9. Test OAuth and bot installation via mocks; no production API calls or real credentials in tests.

## Relevant code
ai_assistant/bots/premium_discord_policy.py
ai_assistant/bots/premium_discord_oauth.py
ai_assistant/bots/premium_discord_discord_api.py
ai_assistant/bots/premium_discord_views.py
ai_assistant/bots/premium_discord_guild_service.py
ai_assistant/bots/premium_discord_chat.py
ai_assistant/bots/premium_discord_interactions.py
ai_assistant/bots/premium_discord_queue.py
ai_assistant/bots/premium_discord_worker.py
ai_assistant/bots/premium_discord_signature.py
ai_assistant/bots/premium_discord_models.py
ai_assistant/bots/migrations/0027_premium_discord_guild.py
ai_assistant/bots/migrations/0028_premium_discord_usage_log.py
ai_assistant/bots/migrations/0029_premium_discord_job.py

## Safe local commands (on feature branch, development database)
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test ai_assistant.bots.test_premium_discord_policy ai_assistant.bots.test_premium_discord_oauth ai_assistant.bots.test_premium_discord_guild_service ai_assistant.bots.test_premium_discord_signature ai_assistant.bots.test_premium_discord_discord_api

Do not run migrations against production, do not use live Discord/OpenAI secrets for tests. Check actual repository manage.py location and active venv first.
