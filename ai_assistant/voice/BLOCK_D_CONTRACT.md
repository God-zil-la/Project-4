# U6.3 Block D – session and mobile web contract

## Scope

The existing conversation bridge (`MyAIStudioVoiceContext`) remains the entry point. It selects an existing assistant/conversation; Live Voice never creates or deletes conversations. The four pre-Block-C sessions without quota reservations remain untouched. Status and stop reject unreserved legacy sessions with HTTP 409 before mutation.

## Existing HTTP routes

- `POST /api/live-voice/start/`: `{assistant_id, conversation_id, request_id}`. `request_id` is a UUID retained across uncertain retries. Same account, request and context return the same session/reservation/deadline, including an already closed session. Rebinding the request to another context fails. Older callers may omit request_id; the new client always supplies it.
- `GET /api/live-voice/<session_id>/`: verifies the owner, settles expired Block C sessions and returns server state. Never cached.
- `POST /api/live-voice/<session_id>/stop/`: idempotent server settlement. Client duration/charge fields are ignored.

All successful lifecycle responses contain `session_id`, `assistant_id`, `conversation_id`, `active`, `server_time`, `deadline_at`, `remaining_ms`, and `ended_at`. `remaining_ms` describes the current session grant, not a fresh monthly allocation. Inactive sessions report zero remaining time. The server owns all quota and elapsed-time decisions.

## Browser lifecycle

- Start binds the server ID before microphone permission. The display derives time from the server observation and deadline, subtracts request latency conservatively and counts down with a monotonic clock. Later replies cannot locally extend the previous grant.
- Status polls every 2 seconds while visible, with at most one status request in flight and an 8-second request timeout. The local cutoff also stops capture if status is delayed.
- **Stop recording** ends a single recording and prepares its voice turn within the current session. **End Live Voice** aborts capture and uploads and requests server settlement.
- Offline, status errors and backgrounding pause capture and cancel uploads/playback. Reconnection checks the same session; the user must tap to record again. Late microphone permissions and stale start/status/upload replies cannot revive the old context.
- A lost start response can be retried with the same request UUID in sessionStorage. No audio upload is automatically retried: an uncertain upload must not trigger duplicate provider work.
- Failed stops remain in a per-tab sessionStorage queue and retry on online/pageshow and every 10 seconds while online. In-flight duplicate stops coalesce. Entries are removed only after a matching inactive server response. Pagehide uses keepalive. If browser storage is disabled, an in-memory fallback remains available for that page.
- Client-side microphone shutdown does not backdate server settlement. During a failed stop request, server elapsed time continues until the stop arrives or the existing deadline is reached. Lost clients are still bounded by Block C's server deadline and reconciliation.

## Provider boundary and remaining work

The Block D client uploads with `prepare_only=true`. The U6.3 upload endpoint bypasses provider dependency resolution for that request and prepares the turn only. No provider flags/configuration or U6.1/U6.2 code were changed. Existing separately configured integrations retain their behavior for other callers.

Real STT transcription, AI answer generation, TTS synthesis and playback of a real generated reply are not activated by this block. They require separately authorized provider integration and a full authorized end-to-end test. Physical iOS/Android microphone permission, backgrounding and browser audio behavior still require device testing. Current client tests execute the actual scripts with browser, microphone and network boundaries replaced locally; they are not physical-device tests.

## Validation

- 345 U6.3 Django tests passed, including 8 new API tests.
- 16 Node client tests passed, executing the actual client scripts, including cancellation races and network recovery.
- Django check: zero issues. No new migration needed.
- Tests use isolated SQLite and fake providers; the MP3 regression fixture is a locally generated tone. PostgreSQL concurrency and physical-device behavior are outside this validation.

Safe regression commands use `--settings=ai_assistant.buildabot.test_settings`. Run Django test modules by their full package names (the repository's directory-only discovery mishandles some relative imports). Node entry point: `node --test ai_assistant/voice/test_block_d_frontend.cjs`.
