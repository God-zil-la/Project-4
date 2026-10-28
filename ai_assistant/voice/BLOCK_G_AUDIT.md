# U6.3 Block G – audit changes and local integration contract

## Safe corrections applied inside U6.3

1. Free mock composition now requires an explicit `VoiceChainProviders.mock_ai` callback. The existing assistant engine still constructs prompts, retrieves knowledge and saves history, but all nested AI provider dispatches in this mock composition route to the supplied local callback, with no implicit fallback to the original OpenAI function. A missing callback refuses processing before STT; a failing callback marks the turn uncertain and never falls back or redispatches. Trusted test callbacks remain server code, not a sandbox; test runs also block all outbound socket connections.
2. The legacy environment-enabled local provider factory now requires both explicit `allow_paid_calls=True` and server setting `U63_EXTERNAL_PROVIDER_APPROVAL=True`. Environment flags alone cannot grant that approval. The setting was not enabled and no real provider composition was installed.
3. Server-owned settlement can finalize a previously reserved session after account deactivation. Public quota commit still refuses inactive principals, and a fresh account-active database filter prevents stale authenticated objects from starting more turn work.
4. Invalid UUID input to session start returns controlled HTTP 400 rather than an unhandled validation exception.
5. Free-chain STT/TTS stage guards now check server time after potentially slow authorization/reservation reads. A regression test demonstrated an expired STT call before the fix; the corrected path refuses it. The existing inner AI provider clock check remains intact.

## Entitlement boundary

Free Live Voice remains restricted to ordinary, unambiguous Free accounts and 600,000 ms per UTC month. Premium, Pro, unknown plans, active K1 and complimentary entitlements do not receive Free reservation credits. Expired K1 may return to the existing Free policy; it does not create a separate campaign allowance in the Free ledger. U6.2's effective Premium/Pro authorization, including effective Pro from active K1, is unchanged. U6.1 retains its separately verified subscription-period policy.

Unified paid/K1 Live Voice sessions are not implemented by the Free pipeline. They require an explicit product and quota-integration decision; the audit did not broaden entitlements or fabricate paid subscription evidence.

## Concurrency, retries and failures

Real two-thread SQLite tests verify that parallel sessions and same-start retries cannot overreserve the monthly limit or produce two sessions for the same start identity. SQLite contention can still reject a competing request with a transient lock error; it fails closed and must be retried after rollback. PostgreSQL lock contention was not tested locally. One processing turn per session, persistent stage claims, request/audio binding and server-authoritative stop prevent duplicate voice/provider debits. Lost HTTP responses are recovered by status/audio GET, not automatic audio repost.

Audio uses authenticated session/turn routes, owner-private storage, internal UUID keys, output hashes and bounded reads. Transcripts are bound to the owner/session/conversation; the existing assistant message-save transaction remains authoritative. The local audio store enforces logical TTL for retrieval but does not automatically delete expired/orphan files. A cleanup/retention policy remains a real-provider prerequisite.

## Outside-scope finding requiring approval

U6.2's `tts.authorization.authorize` wraps transient SQLite OperationalError as AuthorizationDenied. The existing TTS atomic retry only retries OperationalError, so a concurrent TTS test fails. A deterministic work-directory reproducer confirms the failure without any U6.2 edit or provider access.

An unapplied, narrow proposal is supplied in `Block-G-U62-korrigeringsforslag.diff`: preserve only SQLite lock errors for the existing retry mechanism; retain denial for other database/auth failures. This file has not been applied. User approval is required by Block G section 5 before changing the U6.2 source.

The known K1 campaign web-test text expectation still fails in isolation. K1 source and its tests were not changed.

## Validation and next steps

See the delivery report for exact test counts and baseline/finding separation. No migrations were added; local U6.3 remains at 0001–0005. The four legacy sessions and existing application data remain unchanged. No physical Android/iOS or PostgreSQL verification was performed. Provider prices/configuration are documented as estimates only; no external AI calls or costs occurred.

The U6.3 source is ready for a bounded source-review/Git-selection preparation, with the U6.2 finding and known K1 failure explicitly carried forward. This is not a fully green integrated-release or real-provider approval. No Git mutations, commits, merges, pushes, deploys or production changes were performed.
