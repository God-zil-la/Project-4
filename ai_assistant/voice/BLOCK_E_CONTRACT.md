# U6.3 Block E – Free voice chain contract

## Scope and defaults

The server and mobile web client now have a complete microphone/upload → STT → existing AI conversation engine → TTS → private MP3 delivery/playback integration. This implementation is verified using local STT/TTS doubles, a locally generated MP3 fixture and mocked external AI/KB calls. It does not recognize real speech or generate real spoken answers by default.

No external-cost approval is inferred from this block. Provider composition is absent by default, and `process_voice=true` returns 503 without creating a turn if no permitted provider composition exists. The code unconditionally rejects `VoiceChainProviders(external_calls=True)` in this block.

A trusted local test composition uses the context manager `voice_chain_providers(VoiceChainProviders(transcribe, synthesize))`, `DEBUG=True` and `U63_VOICE_TEST_DOUBLES=True`. ContextVars isolate provider composition per execution context. Neither cookies, request flags nor uploaded data can install providers. Test code replaces every external AI/KB boundary and blocks socket connections while executing the real chat engine. The test flag is not itself an AI provider substitute; do not enable it with an unmocked AI engine.

## Existing authenticated endpoints

- Upload: `POST /api/live-voice/<session_id>/upload/`, multipart `audio`, UUID `request_id`, `process_voice=true`.
- Status: `GET /api/live-voice/<session_id>/turns/<request_id>/`.
- MP3: `GET /api/live-voice/<session_id>/turns/<request_id>/audio/`.
- Existing Block C/D start, session status and idempotent stop remain authoritative.

The new client requests processing rather than Block D's prepare-only path. Older requests using `prepare_only=true` retain preparation-only behavior. No route or provider flag outside U6.3 was changed.

## Persisted identity and at-most-once stages

The existing VoiceTurn unique `(session, request_id)` constraint and audio fingerprint reject identity reuse with different input. A committed compare-and-swap changes `created` to `transcribing` before STT. Existing U6.3 AI and TTS claims similarly persist `processing` and `synthesizing` before calling their respective boundaries. The session row is locked when claiming STT; a different active turn in the same session is refused before provider dispatch.

Replays only report state and retrieve already stored audio. They never automatically rerun STT, the assistant engine or TTS. A crash or uncertain provider outcome may leave a turn unfinished/uncertain, which requires reconciliation or an explicit new user turn, not automatic redispatch.

The actual existing `process_bot_message` path supplies assistant personality, instructions, knowledge retrieval, history, account message allowances, usage logging and atomic message saving/VoiceTurn binding. No alternate assistant logic or duplicate message-save path is implemented. Existing chat message quotas continue to apply in addition to the Free session's elapsed-time quota.

## Compatibility with U6.1 / U6.2

The existing U6.1/U6.2 quota/authorization layers require Premium/Pro and are not used to authorize Free sessions. Their source and entitlement rules remain unchanged. Compatible existing WAV validation, the U6.3 AI adapter, MP3 validation and private local audio store are reused.

Migration 0005 adds `output_audio_key` and `output_audio_sha256` to VoiceTurn. Output is stored under the authenticated account and a random internal UUID, bound to the completed turn and saved assistant message. Delivery checks session ownership/validity, completion, output hash, format and existing storage TTL. Internal filenames/keys are not exposed by the HTTP response. Corrupt or missing audio fails closed and never triggers new TTS.

## Deadline, stop and cancellation

Every STT/AI/TTS stage checks the session before and after its potentially slow boundary. A stopped/expired/unreserved or finalized reservation fails closed. Silence, recording and processing continue to count toward Block C's server deadline. No per-turn Live Voice debit is added. Replays do not debit a second time.

If expiry occurs during STT, AI never starts. If it occurs during AI, a safely saved exchange remains in history, but TTS does not start. If it occurs during TTS, output is not published for playback. Client cancellation cannot undo an external operation already dispatched; the next stage and playback remain blocked. Unpublished local output can remain as an inaccessible storage orphan; automatic disk cleanup is not added in this block.

Before any future paid integration, a deadline/cancellation hook is also needed at the existing AI engine's *internal* provider boundary for auxiliary domain/KB calls and long-answer continuations. The current U6.3 code guards the engine invocation as a stage, not each internal provider invocation. No changes to U1–U5 were authorized or made. Paid mode remains rejected, so this limitation cannot enable a paid call in this block.

## Mobile web behavior

The UI shows Lyssnar, Bearbetar and Svarar. Stop recording sends a turn; End Live Voice stops capture, pending HTTP work and playback and requests idempotent session settlement. No automatic microphone restart occurs.

Turn request identities are retained in per-tab sessionStorage for status/audio recovery. A lost response or client timeout is recovered by GET against the same turn, never by automatic audio re-upload. Requests/polls have a 45-second client timeout and bounded status polling. A server may still finish after a disconnected client; recovery never creates another dispatch. Manual Check reply and Play AI reply buttons handle recovery and mobile autoplay restrictions. Pending unresolved replies prevent new recording until checked or the session is ended.

## Validation and next step

- 360 U6.3 Django tests passed, including 15 new Block E tests.
- 22 client tests passed, including 6 new playback/recovery cases.
- Django check: zero issues; model/migration check clean.
- Migration 0005 applied only to the named local SQLite database after backup.
- All four protected legacy session records, pre-existing voice-turn fields, conversations, messages, assistants, user data and quotas remain unchanged by the schema migration.

Ready for Block F local/mock integration and physical-client permission/cancellation/playback checks using a deliberately isolated mock backend. A real microphone-to-AI-to-real-speech device test remains pending separate cost approval, verified STT/TTS provider composition, the AI internal-dispatch deadline hook, device validation and a bounded real-call budget. Current automated browser tests replace browser/media/network boundaries; PostgreSQL lock contention and physical devices have not been validated.
