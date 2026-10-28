/* U6.3 voice playback. No mock audio or provider activation. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-u63-live-voice]").forEach(root => {
      let player = null;
      let generation = 0;

      function stopPlayback() {
        generation += 1;

        if (player) {
          player.pause();
          player.removeAttribute("src");
          player.load();
          player = null;
        }
      }

      root.addEventListener("u63:conversation-changed", stopPlayback);

      root.addEventListener("u63:play-audio", async event => {
        const detail = event.detail || {};
        const url = detail.audio_url;

        if (typeof url !== "string") return;

        // Accept only same-origin HTTPS/HTTP audio endpoints.
        let parsed;
        try {
          parsed = new URL(url, window.location.origin);
        } catch (_) {
          return;
        }

        if (parsed.origin !== window.location.origin) return;
        if (!parsed.pathname.startsWith("/api/live-voice/")) return;

        stopPlayback();

        const currentGeneration = generation;
        const sessionId = root.dataset.voiceSessionId;

        if (!sessionId) return;

        const expectedPrefix =
          `/api/live-voice/${encodeURIComponent(sessionId)}/`;

        if (!parsed.pathname.startsWith(expectedPrefix)) return;

        player = new Audio(parsed.href);
        player.preload = "auto";

        try {
          await player.play();
        } catch (_) {
          if (currentGeneration === generation) {
            const label = root.querySelector(".u63-status");
            if (label) {
              label.textContent =
                "Audio playback unavailable. Tap to retry.";
            }
          }
        }
      });

      root.addEventListener("u63:voice-stopped", stopPlayback);
      root.addEventListener("u63:voice-paused", stopPlayback);
    });
  });
})();
