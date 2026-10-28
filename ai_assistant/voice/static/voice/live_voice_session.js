/* U6.3 server-authoritative session controller. Never extends a server grant. */
(function () {
  "use strict";
  const POLL_MS = 2000;
  class VoiceSessionController {
    constructor(root) {
      this.root = root;
      root._u63SessionController = this;
      this.sessionId = root.dataset.voiceSessionId || null;
      this.verified = false;
      this.budgetUntil = 0;
      this.generation = 0;
      this.pending = false;
      this.checking = null;
      this.startButton = root.querySelector("[data-voice-start]");
      this.endButton = root.querySelector("[data-voice-end]");
      this.timeLabel = root.querySelector("[data-voice-remaining]");
      this.startButton.addEventListener("click", event => {
        event.preventDefault();
        event.stopImmediatePropagation();
        void this.start();
      }, true);
      this.endButton.addEventListener("click", () => { void this.stop(); });
      root.addEventListener("u63:conversation-changed", () => this.invalidate());
      root.addEventListener("u63:session-invalidated", event => {
        if (event.detail.sessionId === this.sessionId) this.invalidate();
      });
      window.addEventListener("offline", () => this.pause("Connection lost. Recording paused."));
      window.addEventListener("online", () => { void this.check(); });
      window.addEventListener("pagehide", () => this.pause("Voice paused."));
      window.addEventListener("pageshow", () => { void this.check(); });
      document.addEventListener("visibilitychange", () => {
        if (document.hidden) this.pause("Voice paused while the app is in the background.");
        else void this.check();
      });
      setInterval(() => this.tick(), 250);
      setInterval(() => { if (!document.hidden) void this.check(); }, POLL_MS);
      this.controls();
    }
    label(text) { this.root.querySelector(".u63-status").textContent = text; }
    remaining() { return Math.max(0, Math.floor(this.budgetUntil - performance.now())); }
    canRecord() {
      return this.verified && !!this.sessionId && this.sessionId === this.root.dataset.voiceSessionId &&
        !window.MyAIStudioVoiceSessions?.isPending(this.sessionId) &&
        navigator.onLine !== false && !document.hidden && this.remaining() > 0;
    }
    controls() {
      this.startButton.disabled = this.pending || Boolean(this.root._u63VoiceTurnBusy) || Boolean(this.root._u63VoiceInstance?.isRecording) ||
        Boolean(this.sessionId && !this.canRecord());
      this.endButton.disabled = !this.sessionId;
    }
    silence(eventName) {
      // abort() stops hardware synchronously before awaiting AudioContext shutdown.
      const operation = this.root._u63VoiceInstance?.abort();
      if (operation?.catch) operation.catch(() => {});
      this.root.dispatchEvent(new CustomEvent(eventName, { bubbles: true }));
      const audio = this.root.querySelector("[data-voice-audio]");
      if (audio) { audio.pause(); audio.removeAttribute("src"); audio.load(); audio.hidden = true; }
      const play = this.root.querySelector("[data-voice-play]");
      if (play) play.disabled = true;
    }
    pause(message) {
      this.verified = false;
      this.silence("u63:voice-paused");
      this.controls();
      this.label(message);
    }
    invalidate() {
      ++this.generation;
      this.verified = false;
      this.sessionId = null;
      this.budgetUntil = 0;
      delete this.root.dataset.voiceSessionId;
      this.silence("u63:voice-stopped");
      this.controls();
      this.tick();
    }
    tick() {
      const remaining = this.remaining();
      if (this.timeLabel) {
        const seconds = Math.ceil(remaining / 1000);
        this.timeLabel.textContent = `Live Voice time: ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
      }
      if (this.sessionId && this.budgetUntil && !remaining) {
        void this.stop("Live Voice time has ended.");
      }
      this.controls();
    }
    key(assistantId, conversationId) { return `u63.start.v1.${assistantId}.${conversationId}`; }
    read(key) { try { return sessionStorage.getItem(key) || this.startRequests?.[key]; } catch (_) { return this.startRequests?.[key]; } }
    write(key, value) {
      this.startRequests ||= {};
      if (value) this.startRequests[key] = value; else delete this.startRequests[key];
      try { if (value) sessionStorage.setItem(key, value); else sessionStorage.removeItem(key); } catch (_) {}
    }
    async request(url, options = {}) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch(url, { credentials: "same-origin", cache: "no-store", ...options, signal: controller.signal });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const error = new Error(data.error || "Voice session unavailable.");
          error.status = response.status;
          throw error;
        }
        return data;
      } finally { clearTimeout(timeout); }
    }
    apply(data, began) {
      if (data.session_id !== this.sessionId ||
          String(data.assistant_id) !== this.root.dataset.assistantId ||
          data.conversation_id !== this.root.dataset.conversationId ||
          typeof data.active !== "boolean" ||
          !Number.isSafeInteger(data.remaining_ms) || data.remaining_ms < 0 || data.remaining_ms > 600000 ||
          !Number.isFinite(Date.parse(data.server_time)) || !Number.isFinite(Date.parse(data.deadline_at))) {
        throw new Error("Invalid server session status.");
      }
      const remaining = Math.max(0, Math.min(data.remaining_ms,
        Date.parse(data.deadline_at) - Date.parse(data.server_time)) - (performance.now() - began));
      const next = performance.now() + remaining;
      // Even later status replies cannot locally lengthen this session's grant.
      this.budgetUntil = this.budgetUntil ? Math.min(this.budgetUntil, next) : next;
      if (!data.active || remaining <= 0 || this.remaining() <= 0) {
        if (data.active) void this.stop("Live Voice time has ended.");
        else {
          this.write(this.key(this.root.dataset.assistantId, this.root.dataset.conversationId), null);
          this.invalidate();
          this.label("Live Voice session ended.");
        }
        return false;
      }
      this.verified = true;
      this.root.dispatchEvent(new CustomEvent("u63:session-verified", { bubbles: true }));
      this.controls();
      this.tick();
      return true;
    }
    async start() {
      if (this.pending) return;
      const assistantId = this.root.dataset.assistantId;
      const conversationId = this.root.dataset.conversationId;
      if (!assistantId || !conversationId) {
        this.label("Select an existing conversation to enable Live Voice.");
        return;
      }
      if (navigator.onLine === false || document.hidden) return;
      this.pending = true;
      this.controls();
      const generation = this.generation;
      const key = this.key(assistantId, conversationId);
      const csrf = document.cookie.split("; ").find(value => value.startsWith("csrftoken="));
      try {
        if (!this.sessionId) {
          if (!csrf) throw new Error("CSRF token unavailable.");
          const requestId = this.read(key) || crypto.randomUUID();
          this.write(key, requestId);
          const began = performance.now();
          const data = await this.request("/api/live-voice/start/", {
            method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf.slice(10)) },
            body: JSON.stringify({ assistant_id: assistantId, conversation_id: conversationId, request_id: requestId })
          });
          if (!data.session_id) throw new Error("Missing server session identity.");
          if (generation !== this.generation || assistantId !== this.root.dataset.assistantId || conversationId !== this.root.dataset.conversationId) {
            void window.MyAIStudioVoiceSessions.closeSession(data.session_id);
            this.write(key, null);
            return;
          }
          if (window.MyAIStudioVoiceSessions.isPending(data.session_id)) {
            this.write(key, null);
            throw new Error("Previous session is closing. Tap start again.");
          }
          this.sessionId = data.session_id;
          this.root.dataset.voiceSessionId = data.session_id;
          if (!this.apply(data, began)) { this.write(key, null); return; }
          this.root.dispatchEvent(new CustomEvent("u63:session-started", { bubbles: true, detail: { sessionId: data.session_id } }));
        } else if (!await this.check()) return;
        if (generation === this.generation && this.canRecord()) {
          await this.root._u63VoiceInstance?.start();
        }
      } catch (error) {
        if (generation === this.generation) {
          if (error.status && error.status < 500) this.write(key, null);
          this.pause(error.message || "Could not connect. Tap start to retry.");
        }
      } finally { this.pending = false; this.controls(); }
    }
    async check() {
      if (!this.sessionId || navigator.onLine === false || document.hidden) return false;
      if (this.checking) return this.checking;
      const id = this.sessionId;
      const generation = this.generation;
      const began = performance.now();
      const operation = (async () => {
        try {
          const data = await this.request(`/api/live-voice/${encodeURIComponent(id)}/`);
          if (generation !== this.generation || id !== this.sessionId) return false;
          const wasPaused = !this.verified;
          const active = this.apply(data, began);
          if (active && wasPaused) this.label("Session reconnected. Tap Start recording to continue.");
          return active;
        } catch (error) {
          if (generation !== this.generation) return false;
          if ([401, 403, 404, 409].includes(error.status)) {
            void this.stop("Voice session unavailable. Start a new session.");
          } else this.pause("Connection unavailable. Recording paused; checking the same session.");
          return false;
        }
      })();
      this.checking = operation;
      try { return await operation; } finally { if (this.checking === operation) this.checking = null; }
    }
    async stop(message = "Live Voice session ended.") {
      const id = this.sessionId;
      if (!id) return;
      this.write(this.key(this.root.dataset.assistantId, this.root.dataset.conversationId), null);
      this.invalidate();
      this.label(message);
      const settled = await window.MyAIStudioVoiceSessions.closeSession(id);
      if (!settled && !this.sessionId) this.label("Recording stopped. Server stop pending; it will retry when connected.");
    }
  }
  window.MyAIStudioVoiceSessionController = VoiceSessionController;
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-u63-live-voice]").forEach(root => new VoiceSessionController(root));
  });
})();
