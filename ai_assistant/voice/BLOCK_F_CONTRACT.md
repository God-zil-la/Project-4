# U6.3 Block F – provider deadline and mobile mock verification

## Status

Local implementation and automated safety verification are complete. Block F remains **partially complete overall** because no physical Android or iOS device test was available. External voice/AI providers remain disabled; this block grants no external-cost approval.

## Minimal engine integration

The four engine modules `chat_service`, `knowledge_utils`, `document_ai_intent` and `document_workbook` now import `provider_call` through U6.3's `provider_boundary`. Those four existing source changes are exactly one import replacement per file; their assistant, knowledge, document and text-chat algorithms are unchanged. K1's campaign code and other U6 subsystems were not edited.

`ai_adapter.process_voice_answer` establishes `voice_provider_scope` only around the existing assistant-engine invocation. A ContextVar carries authenticated user/session/turn identity through synchronous nested helper calls and restores the previous context even on failure. Other execution contexts do not inherit that scope accidentally.

Without an active U6.3 scope, the bridge forwards the original callable and arguments to the original campaign/billing function, without reading voice tables or applying voice deadlines. Text chat and other integrations keep their prior behavior.

Within a scope, authorization checks occur before the original billing function and again inside its actual `create` callback immediately before invoking the provider. Checks read the active account, server session/deadline, Free eligibility, still-reserved session quota and the exact processing turn. A final server clock check occurs after potentially slow authorization/database reads. A deadline reached at equality blocks the call. No transaction or lock is held open across an external provider operation.

This covers the current engine's final-answer and continuation calls, knowledge planning/classification, domain follow-up review, embedding batches and document helpers. A previously dispatched operation cannot be undone; after expiry no subsequent provider call is allowed. Block E still checks STT/AI/TTS before and after each stage and prevents new TTS/audio publication after expiry. Already saved conversation records remain intact.

## Verification

Final combined backend run: **439 tests, 438 passed, 1 failed**. All **376 U6.3 tests passed**, including 16 Block F tests. Of 63 additional shared-engine/text/knowledge/document/campaign regressions, 62 passed and one existing campaign page-text expectation failed.

The failing test is `ai_assistant.accounts.test_campaign.CampaignTests.test_web_requires_session_csrf_and_post`. It expects the text `Your free Pro campaign has started.`. An isolated baseline run restoring all four original provider functions reproduces that same failure; the test's page-text mismatch is independent of the new provider deadline bridge. K1 code and the test were left unchanged.

The combined backend run used an explicitly fake API key and blocked socket connections. All provider responses used for deadline/voice verification were local doubles. A missing fake key and a working-directory dependency in older tests were corrected in the temporary test runner, not in product code.

Client verification: **28/28 tests passed**, executing the actual client scripts in a Node VM with simulated DOM/media/fetch boundaries. Six Block F cases cover Android-style behavior, iOS-style `webkitAudioContext` fallback, denied microphone permission, processing/upload/playback, background/foreground, manual recording restart, request timeout and same-turn GET-only network recovery. The existing cases cover local deadline cutoff, lifecycle, playback interruption, autoplay recovery and duplicate POST prevention.

These are **not physical-device tests and not actual Chrome/WebKit browser-engine emulation**. Setting simulated mobile profiles does not establish hardware/browser compatibility.

## Physical device availability

- Android: `adb devices -l` returned an empty attached-device list. No physical Android tests were performed.
- iOS: no physical-device execution channel or macOS/iOS simulator was available in this environment. No physical iOS tests were performed.
- Physical device tests passed: **0**; failed physical tests: **0**; the requested device matrix remains unexecuted.

## Other checks and protected data

Django check reported no issues. Full `makemigrations --check --dry-run` reported no changes; the local U6.3 migration list remains 0001–0005. No schema or local database mutation was made in Block F.

Read-only checks confirmed that the four protected legacy session records and prior application data are unchanged, SQLite integrity is OK and foreign-key violations are zero. No retroactive quota debit occurred. Source backups contain only the existing files changed by Block F.

## Before real voice testing

Separate explicit cost approval, a bounded call budget, trusted server-side STT/AI/TTS provider composition, credentials and controlled failure/timeouts remain required. Block E's external-provider mode remains rejected and no providers were installed by Block F. The internal AI provider-deadline prerequisite from Block E is now implemented and mock-verified.

Physical Android/iOS testing should first use a deliberately isolated mock backend; only later should a separately approved real-call budget be used. PostgreSQL contention and physical microphone, audio routing, mobile autoplay and OS background suspension remain unverified here. Existing crash/uncertain-turn reconciliation limitations from Block E remain.

No commit, push, merge, deploy or production changes were made.
