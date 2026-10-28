/* U6.3: idempotent, retryable session settlement. No provider requests. */
(function () {
  "use strict";
  const KEY = "u63.pending-stops.v1";
  const pending = new Set();
  const inflight = new Map();
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  try {
    const stored = JSON.parse(sessionStorage.getItem(KEY) || "[]");
    if (Array.isArray(stored)) stored.filter(id => UUID.test(id)).forEach(id => pending.add(id));
  } catch (_) { /* In-memory retry remains available if browser storage is disabled. */ }
  function save() {
    try { sessionStorage.setItem(KEY, JSON.stringify([...pending])); } catch (_) {}
  }
  function csrf() {
    const item = document.cookie.split("; ").find(value => value.startsWith("csrftoken="));
    return item ? decodeURIComponent(item.slice(10)) : "";
  }
  function closeSession(sessionId) {
    if (!UUID.test(sessionId || "")) return Promise.resolve(false);
    pending.add(sessionId);
    save();
    if (inflight.has(sessionId)) return inflight.get(sessionId);
    const operation = (async () => {
      const token = csrf();
      if (!token) return false;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch(`/api/live-voice/${encodeURIComponent(sessionId)}/stop/`, {
          method: "POST", credentials: "same-origin", keepalive: true,
          headers: { "X-CSRFToken": token }, signal: controller.signal
        });
        const result = await response.json().catch(() => ({}));
        if (response.ok && result.session_id === sessionId && result.active === false) {
          pending.delete(sessionId);
          save();
          return true;
        }
        return false;
      } catch (_) { return false; }
      finally { clearTimeout(timeout); }
    })();
    inflight.set(sessionId, operation);
    operation.finally(() => inflight.delete(sessionId));
    return operation;
  }
  async function retryPending() {
    return Promise.all([...pending].map(closeSession));
  }
  window.MyAIStudioVoiceSessions = { closeSession, retryPending, isPending: id => pending.has(id) };
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-u63-live-voice]").forEach(root => {
      root.addEventListener("u63:session-invalidated", event => {
        void closeSession(event.detail.sessionId);
      });
      window.addEventListener("pagehide", () => {
        void closeSession(root.dataset.voiceSessionId);
      });
    });
    window.addEventListener("online", () => { void retryPending(); });
    window.addEventListener("pageshow", () => { void retryPending(); });
    setInterval(() => { if (pending.size && navigator.onLine !== false) void retryPending(); }, 10000);
    void retryPending();
  });
})();
