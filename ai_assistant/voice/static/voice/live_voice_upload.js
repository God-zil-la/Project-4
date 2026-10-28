/* U6.3 voice turn upload, status recovery and generated audio playback. */
(function () {
  "use strict";
  const MAX_BYTES = 10 * 1024 * 1024;
  const POLL_MS = 1200;
  const MAX_POLLS = 25;
  class VoiceTurnClient {
    constructor(root) {
      this.root = root;
      root._u63TurnClient = this;
      this.generation = 0;
      this.controller = null;
      this.busy = false;
      this.player = null;
      this.audioUrl = null;
      this.pending = null;
      root.addEventListener("u63:audio-ready", event => { void this.upload(event.detail); });
      root.addEventListener("u63:voice-paused", () => this.cancel(false));
      root.addEventListener("u63:voice-stopped", () => this.cancel(true));
      root.addEventListener("u63:conversation-changed", () => this.cancel(true));
      root.addEventListener("u63:session-verified", () => { void this.recover(); });
      root.addEventListener("u63:session-started", () => { void this.recover(); });
      root.querySelector("[data-voice-reply]").addEventListener("click", () => { void this.play(); });
      root.querySelector("[data-voice-recover]").addEventListener("click", () => { void this.recover(); });
    }
    label(text) { this.root.querySelector(".u63-status").textContent = text; }
    key(id) { return `u63.turn.v1.${id}`; }
    save(task) {
      this.pending = task;
      try { sessionStorage.setItem(this.key(task.sessionId), JSON.stringify(task)); } catch (_) {}
    }
    forget() {
      if (this.pending) {
        try { sessionStorage.removeItem(this.key(this.pending.sessionId)); } catch (_) {}
      }
      this.pending = null;
      this.root.querySelector("[data-voice-recover]").disabled = true;
    }
    setBusy(value) {
      this.busy = value;
      this.root._u63VoiceTurnBusy = value;
      this.root._u63SessionController?.controls();
    }
    playable() {
      return !!this.audioUrl && this.root._u63SessionController?.canRecord();
    }
    stopPlayback() {
      if (this.player) { this.player.pause(); this.player.removeAttribute("src"); this.player.load(); }
      this.player = null;
      if (this.audioUrl) URL.revokeObjectURL(this.audioUrl);
      this.audioUrl = null;
      this.root.querySelector("[data-voice-reply]").disabled = true;
    }
    cancel(forget) {
      ++this.generation;
      this.controller?.abort();
      this.controller = null;
      this.stopPlayback();
      this.setBusy(false);
      if (forget) this.forget();
    }
    current(task, generation, signal) {
      return generation === this.generation && !signal.aborted &&
        this.root.dataset.voiceSessionId === task.sessionId &&
        this.root.dataset.conversationId === task.conversationId &&
        this.root._u63SessionController?.canRecord();
    }
    async fetchResponse(url, options, signal) {
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store", ...options, signal });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        const error = new Error(result.error || "Voice response unavailable.");
        error.status = response.status;
        throw error;
      }
      return response;
    }
    async play() {
      if (!this.playable() || !this.player) return;
      const player = this.player;
      const generation = this.generation;
      try {
        await player.play();
        if (generation !== this.generation || !this.playable()) { player.pause(); return; }
        this.label("Svarar…");
      } catch (_) {
        if (generation === this.generation && this.playable()) this.label("Tap Play AI reply to hear the saved response.");
      }
    }
    async awaitReply(task, generation, signal) {
      const prefix = `/api/live-voice/${encodeURIComponent(task.sessionId)}/turns/${encodeURIComponent(task.requestId)}/`;
      for (let n = 0; n < MAX_POLLS; n++) {
        if (!this.current(task, generation, signal)) return;
        let data;
        try { data = await (await this.fetchResponse(prefix, {}, signal)).json(); }
        catch (error) { if (error.status !== 404 || n === MAX_POLLS - 1) throw error; }
        if (data) {
          if (data.session_id !== task.sessionId || data.request_id !== task.requestId) throw new Error("Voice identity mismatch.");
          if (["failed", "uncertain", "cancelled", "canceled"].includes(data.state)) {
            this.forget();
            throw new Error("Voice processing stopped safely. It will not be repeated automatically.");
          }
          if (data.state === "completed" && data.has_assistant_answer === true) {
            const response = await this.fetchResponse(prefix + "audio/", {}, signal);
            if (!(response.headers.get("content-type") || "").toLowerCase().startsWith("audio/mpeg")) throw new Error("Invalid audio response.");
            const blob = await response.blob();
            if (!this.current(task, generation, signal)) return;
            this.stopPlayback();
            this.audioUrl = URL.createObjectURL(blob);
            this.player = new Audio(this.audioUrl);
            this.player.onended = () => {
              if (this.current(task, generation, signal)) this.label("Reply finished. Tap Start recording to continue.");
            };
            this.player.onerror = () => this.label("Audio playback failed. Check the saved conversation.");
            this.root.querySelector("[data-voice-reply]").disabled = false;
            this.forget();
            await this.play();
            return;
          }
        }
        await new Promise((resolve, reject) => {
          const timer = setTimeout(done, POLL_MS);
          function done() { signal.removeEventListener("abort", abort); resolve(); }
          function abort() { clearTimeout(timer); signal.removeEventListener("abort", abort); reject(new DOMException("Cancelled", "AbortError")); }
          if (signal.aborted) abort(); else signal.addEventListener("abort", abort, {once:true});
        });
      }
      throw new Error("Voice processing is taking longer. Use Check reply; do not resend the recording.");
    }
    async run(task, wav) {
      this.setBusy(true);
      this.stopPlayback();
      const generation = ++this.generation;
      const controller = new AbortController();
      this.controller = controller;
      const timeout = setTimeout(() => controller.abort(), 45000);
      try {
        this.label("Bearbetar…");
        if (wav) {
          const item = document.cookie.split("; ").find(value => value.startsWith("csrftoken="));
          if (!item) throw new Error("CSRF token unavailable.");
          const body = new FormData();
          body.append("audio", wav, "voice.wav");
          body.append("request_id", task.requestId);
          body.append("process_voice", "true");
          const response = await this.fetchResponse(`/api/live-voice/${encodeURIComponent(task.sessionId)}/upload/`, {
            method: "POST", headers: {"X-CSRFToken":decodeURIComponent(item.slice(10))}, body
          }, controller.signal);
          const data = await response.json();
          if (data.session_id !== task.sessionId || data.request_id !== task.requestId) throw new Error("Voice identity mismatch.");
          if (!data.result) { this.forget(); throw new Error("Voice processing is not configured."); }
          if (!this.current(task, generation, controller.signal)) return;
          this.root.dispatchEvent(new CustomEvent("u63:upload-complete", {bubbles:true,detail:data}));
        }
        await this.awaitReply(task, generation, controller.signal);
      } catch (error) {
        if (generation === this.generation) {
          // Never resend a POST after uncertain network/provider outcomes.
          if ([400,401,403,409,503].includes(error.status)) this.forget();
          if (this.pending) {
            this.root.querySelector("[data-voice-recover]").disabled = false;
            this.label("Connection interrupted or timed out. Check reply to recover the same turn.");
          } else this.label(error.message || "Voice response unavailable.");
        }
      } finally {
        clearTimeout(timeout);
        if (generation === this.generation) this.setBusy(false);
        if (this.controller === controller) this.controller = null;
      }
    }
    async upload(detail = {}) {
      if (this.busy || !this.root._u63SessionController?.canRecord()) return;
      if (detail.sessionId !== this.root.dataset.voiceSessionId || detail.conversationId !== this.root.dataset.conversationId) return;
      if (!(detail.wav instanceof Blob) || !detail.wav.size || detail.wav.size > MAX_BYTES) { this.label("Invalid audio size."); return; }
      if (this.pending) { this.label("Check the previous reply before recording again."); return; }
      const task = { sessionId:detail.sessionId, conversationId:detail.conversationId, requestId:crypto.randomUUID() };
      this.save(task);
      await this.run(task, detail.wav);
    }
    async recover() {
      if (this.busy || !this.root._u63SessionController?.canRecord()) return;
      if (!this.pending) {
        try { this.pending = JSON.parse(sessionStorage.getItem(this.key(this.root.dataset.voiceSessionId)) || "null"); } catch (_) {}
      }
      const task = this.pending;
      if (!task || task.sessionId !== this.root.dataset.voiceSessionId || task.conversationId !== this.root.dataset.conversationId ||
          !/^[0-9a-f-]{36}$/i.test(task.requestId || "")) return;
      await this.run(task, null);
    }
  }
  window.MyAIStudioVoiceTurnClient = VoiceTurnClient;
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-u63-live-voice]").forEach(root => new VoiceTurnClient(root));
  });
})();
