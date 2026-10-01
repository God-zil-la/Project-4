# Android AI response reports

Deploy the backend and run `python manage.py migrate` before distributing the
updated Android app. Migration `bots.0020_ai_response_reports` only adds the
report table, its foreign keys, unique constraint and reporter/time index. It
does not change existing chat data. No new dependencies or environment variables
are required. Release a new Android build through the existing release process.

Android assistant messages have **Report response**. The native confirmation
explains that a copy of the response is sent to the developers for review.
Cancel sends nothing. Success is acknowledged beside the message; failures
remain retryable. iOS and web do not render this action.

`POST /bots/api/conversations/{conversation_uuid}/messages/{message_id}/report/`
uses the existing token/session authentication and an empty JSON object (`{}`).
Only assistant messages visible through that user's conversation history can be
reported, including owner-visible visitor conversations. Nonexistent or
inaccessible messages return 404. Client-supplied evidence or ownership fields
are rejected. No AI request, email or external page is involved.

New reports return 201 with `{ "id": 1, "reported": true }`. Duplicate reports
return the original receipt with 200. Each user can submit 20 new reports per
rolling 24 hours; excess requests return 429 with Retry-After. Existing receipts
remain retryable even at the limit. A database uniqueness constraint prevents
duplicate rows; a per-user database row lock serializes submissions across
PostgreSQL workers. SQLite development tests do not exercise PostgreSQL row-lock
concurrency.

Review reports in Django admin under **AI response reports**. Give the designated
reviewers the model's view/change permissions, then regularly review pending
reports and record the disposition and review notes. Django's admin history
records who changed a report and when. There are no public report-list APIs or
automatic email alerts. Report creation/deletion is disabled in admin, and
evidence fields are read-only.

Reports retain the server-side response text, original message ID, conversation
UUID, response timestamp and report timestamp. If the conversation or account
is deleted, the live references become null and the reported evidence remains
available for investigation. This does not block or change existing deletion
flows. Treat these snapshots as potentially sensitive user content; apply the
service's retention/access policy to this review queue. Reports contain no
copies of the surrounding conversation, email address or auth token.

Before release, smoke-test on an Android device: report a new and a historical
assistant response, cancel a report, retry after a network failure, and verify
the pending record in admin. Also confirm normal sending, scrolling and user
messages are unchanged. The automated component tests mock native primitives;
they do not replace a real Android device check.
