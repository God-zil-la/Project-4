/* My AI Assistant Studio – U6.3 conversation binding.
 *
 * A trusted integration with the existing chat must call:
 * MyAIStudioVoiceContext.set(root, assistantId, conversationId)
 *
 * Conversation changes invalidate the previous voice session.
 */
(function () {
  "use strict";

  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  function bind(root, assistantId, conversationId) {
    if (!(root instanceof HTMLElement) ||
        !root.matches("[data-u63-live-voice]")) {
      throw new Error("Invalid Live Voice component.");
    }

    const assistant = String(assistantId || "");
    const conversation = String(conversationId || "");

    if (!/^[1-9]\d*$/.test(assistant) || !UUID.test(conversation)) {
      throw new Error("Invalid assistant or conversation ID.");
    }

    const previousAssistant = root.dataset.assistantId;
    const previousConversation = root.dataset.conversationId;

    if (previousAssistant === assistant &&
        previousConversation === conversation) {
      return;
    }

    // Never reuse an earlier voice session for another conversation.
    const previousVoiceSessionId = root.dataset.voiceSessionId;
    if (previousVoiceSessionId) {
      root.dispatchEvent(new CustomEvent("u63:session-invalidated", {
        bubbles: true,
        detail: { sessionId: previousVoiceSessionId }
      }));
    }
    delete root.dataset.voiceSessionId;
    root.dataset.assistantId = assistant;
    root.dataset.conversationId = conversation;

    const start = root.querySelector("[data-voice-start]");
    const status = root.querySelector(".u63-status");

    if (start) {
      start.disabled = false;
    }

    if (status) {
      status.textContent = "Ready for voice conversation.";
    }

    root.dispatchEvent(new CustomEvent("u63:conversation-changed", {
      bubbles: true,
      detail: {
        assistantId: assistant,
        conversationId: conversation
      }
    }));
  }

  function clear(root) {
    if (!(root instanceof HTMLElement)) return;

    const previousVoiceSessionId = root.dataset.voiceSessionId;
    if (previousVoiceSessionId) {
      root.dispatchEvent(new CustomEvent("u63:session-invalidated", {
        bubbles: true,
        detail: { sessionId: previousVoiceSessionId }
      }));
    }
    delete root.dataset.voiceSessionId;
    delete root.dataset.assistantId;
    delete root.dataset.conversationId;

    const status = root.querySelector(".u63-status");
    if (status) {
      status.textContent = "Select a conversation to use Live Voice.";
    }
    root.dispatchEvent(new CustomEvent("u63:conversation-changed", {
      bubbles: true,
      detail: { conversationId: null }
    }));

  }

  window.MyAIStudioVoiceContext = {
    set: bind,
    clear
  };
})();
