/* U6.3 ? invalidate stale audio after conversation changes.

   This blocks stale audio from reaching the upload bridge.
   Microphone hardware shutdown must be verified in live_voice.js.
*/
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-u63-live-voice]").forEach(root => {
      let generation = 0;

      // Capture the current context before other listeners process audio.
      root.addEventListener("u63:audio-ready", event => {
        const detail = event.detail || {};

        if (!detail.conversationId ||
            detail.conversationId !== root.dataset.conversationId ||
            !detail.sessionId ||
            detail.sessionId !== root.dataset.voiceSessionId) {
          event.stopImmediatePropagation();
          event.preventDefault();

          const label = root.querySelector(".u63-status");
          if (label) {
            label.textContent =
              "Recording discarded after conversation change.";
          }
          return;
        }

        if (typeof detail.generation === "number" &&
            detail.generation !== generation) {
          event.stopImmediatePropagation();
          event.preventDefault();
        }
      }, true);

      root.addEventListener("u63:conversation-changed", () => {
        generation += 1;

        const component = root._u63VoiceInstance;
        if (component &&
            typeof component.abort === "function") {
          component.abort();
        }
      });
    });
  });
})();
