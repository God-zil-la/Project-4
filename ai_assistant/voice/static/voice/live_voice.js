/* My AI Assistant Studio – U6.3 Live Voice.
 * Standalone browser component. No external requests.
 */
(function () {
  "use strict";

  class LiveVoice {
    constructor(root) {
      this.root = root;
      this.stream = null;
      this.context = null;
      this.processor = null;
      this.source = null;
      this.chunks = [];
      this.isRecording = false;
      this.epoch = 0;
      this.recordingIdentity = null;
      this.audioUrl = null;

      root.innerHTML = `
        <section class="u63-panel" aria-label="Live Voice">
          <div class="u63-orb" aria-hidden="true">🎙️</div>
          <h2>Live Voice</h2>
          <p class="u63-subtitle">
            Talk naturally with your AI assistant
          </p>
          <p class="u63-status" role="status" aria-live="polite">
            Ready to record
          </p>
          <p data-voice-remaining aria-live="off">Live Voice time: --:--</p>
          <div class="u63-controls">
            <button type="button" data-voice-start>Start recording</button>
            <button type="button" data-voice-stop disabled>Stop recording</button>
            <button type="button" data-voice-end disabled>End Live Voice</button>
            <button type="button" data-voice-play disabled>Play recording</button>
            <button type="button" data-voice-reply disabled>Play AI reply</button>
            <button type="button" data-voice-recover disabled>Check reply</button>
          </div>
          <audio data-voice-audio controls hidden></audio>
        </section>
      `;

      this.startButton = root.querySelector("[data-voice-start]");
      this.stopButton = root.querySelector("[data-voice-stop]");
      this.playButton = root.querySelector("[data-voice-play]");
      this.audio = root.querySelector("[data-voice-audio]");
      this.status = root.querySelector(".u63-status");

      this.startButton.addEventListener("click", () => this.start());
      this.stopButton.addEventListener("click", () => this.stop());
      this.playButton.addEventListener("click", () => {
        if (this.audioUrl) this.audio.play();
      });
    }

    setStatus(value) {
      this.status.textContent = value;
    }

    isCurrent(epoch, identity) {
      return (!this.root._u63SessionController || this.root._u63SessionController.canRecord()) &&
        this.epoch === epoch &&
        this.root.dataset.voiceSessionId === identity.sessionId &&
        this.root.dataset.conversationId === identity.conversationId;
    }

    async start() {
      if (this.isRecording || this.starting || this.root._u63VoiceTurnBusy || this.root._u63TurnClient?.pending) return;
      if (this.root._u63SessionController && !this.root._u63SessionController.canRecord()) return;

      const identity = {
        sessionId: this.root.dataset.voiceSessionId,
        conversationId: this.root.dataset.conversationId
      };

      if (!identity.sessionId || !identity.conversationId) {
        this.setStatus("Start a voice session first.");
        return;
      }

      const epoch = ++this.epoch;
      this.starting = true;
      this.startButton.disabled = true;

      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error("Microphone access is unavailable.");
        }

        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true
          }
        });

        if (!this.isCurrent(epoch, identity)) {
          stream.getTracks().forEach(track => track.stop());
          return;
        }

        this.stream = stream;
        const Context = window.AudioContext || window.webkitAudioContext;
        if (!Context) throw new Error("AudioContext unavailable.");

        this.context = new Context();
        this.sampleRate = this.context.sampleRate;
        this.chunks = [];
        this.recordingIdentity = identity;

        this.source = this.context.createMediaStreamSource(stream);
        this.processor = this.context.createScriptProcessor(4096, 1, 1);

        this.processor.onaudioprocess = event => {
          if (!this.isRecording ||
              !this.isCurrent(epoch, identity)) return;

          const samples = event.inputBuffer.getChannelData(0);
          this.chunks.push(new Float32Array(samples));
        };

        this.source.connect(this.processor);
        this.processor.connect(this.context.destination);

        if (!this.isCurrent(epoch, identity)) return;

        this.isRecording = true;
        this.stopButton.disabled = false;
        this.root.classList.add("u63-recording");
        this.setStatus("Lyssnar…");
      } catch (error) {
        if (this.epoch === epoch) {
          this.setStatus(error.message || "Microphone error.");
        }
      } finally {
        if (this.epoch === epoch) {
          if (!this.isRecording) {
            await this.cleanup();
            this.recordingIdentity = null;
          }
          this.starting = false;
          this.startButton.disabled = this.isRecording;
        }
      }
    }

    async abort() {
      ++this.epoch;
      this.isRecording = false;
      this.starting = false;
      this.recordingIdentity = null;
      this.chunks = [];
      this.stopButton.disabled = true;
      this.startButton.disabled = false;
      this.root.classList.remove("u63-recording");

      // Abort must never emit an audio-ready event.
      await this.cleanup();
      if (this.audioUrl) URL.revokeObjectURL(this.audioUrl);
      this.audioUrl = null;
      this.audio.pause();
      this.audio.removeAttribute("src");
      this.audio.load();
      this.audio.hidden = true;
      this.playButton.disabled = true;
      if (!this.root._u63SessionController) this.setStatus("Recording cancelled.");
    }

    async stop() {
      if (!this.isRecording) return;

      const epoch = this.epoch;
      const identity = this.recordingIdentity;

      this.isRecording = false;
      this.stopButton.disabled = true;
      this.root.classList.remove("u63-recording");

      const samples = this.joinSamples(this.chunks);
      const sampleRate = this.sampleRate;

      await this.cleanup();

      // An abort or conversation change may happen during cleanup.
      if (!identity || !this.isCurrent(epoch, identity)) {
        return;
      }

      if (!samples.length) {
        this.setStatus("No audio recorded.");
        this.startButton.disabled = false;
        return;
      }

      const normalizedSamples = this.resampleTo16k(samples, sampleRate);
      const wav = this.encodeWav(normalizedSamples, 16000);

      if (!this.isCurrent(epoch, identity)) return;

      if (this.audioUrl) URL.revokeObjectURL(this.audioUrl);
      this.audioUrl = URL.createObjectURL(wav);

      this.audio.src = this.audioUrl;
      this.audio.hidden = false;
      this.playButton.disabled = false;
      this.startButton.disabled = false;
      this.recordingIdentity = null;
      this.chunks = [];
      this.setStatus("Recording ready.");

      this.root.dispatchEvent(new CustomEvent("u63:audio-ready", {
        detail: {
          wav,
          sessionId: identity.sessionId,
          conversationId: identity.conversationId
        },
        bubbles: true
      }));
    }

    joinSamples(chunks) {
      const total = chunks.reduce((n, chunk) => n + chunk.length, 0);
      const result = new Float32Array(total);
      let offset = 0;

      chunks.forEach(chunk => {
        result.set(chunk, offset);
        offset += chunk.length;
      });

      return result;
    }

    resampleTo16k(samples, inputRate) {
      const outputRate = 16000;

      if (!Number.isFinite(inputRate) || inputRate < outputRate) {
        throw new Error("Unsupported microphone sample rate.");
      }

      if (inputRate === outputRate) {
        return samples;
      }

      const ratio = inputRate / outputRate;
      const outputLength = Math.floor(samples.length / ratio);
      const output = new Float32Array(outputLength);

      for (let i = 0; i < outputLength; i++) {
        const start = Math.floor(i * ratio);
        const end = Math.min(
          samples.length,
          Math.floor((i + 1) * ratio)
        );

        let sum = 0;

        for (let j = start; j < end; j++) {
          sum += samples[j];
        }

        output[i] = end > start
          ? sum / (end - start)
          : 0;
      }

      return output;
    }

    encodeWav(samples, sampleRate) {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);

      const write = (offset, text) => {
        for (let i = 0; i < text.length; i++) {
          view.setUint8(offset + i, text.charCodeAt(i));
        }
      };

      write(0, "RIFF");
      view.setUint32(4, 36 + samples.length * 2, true);
      write(8, "WAVE");
      write(12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      write(36, "data");
      view.setUint32(40, samples.length * 2, true);

      samples.forEach((sample, index) => {
        const normalized = Math.max(-1, Math.min(1, sample));
        view.setInt16(
          44 + index * 2,
          normalized < 0
            ? normalized * 0x8000
            : normalized * 0x7fff,
          true
        );
      });

      return new Blob([buffer], { type: "audio/wav" });
    }

    async cleanup() {
      if (this.processor) {
        this.processor.disconnect();
        this.processor.onaudioprocess = null;
        this.processor = null;
      }

      if (this.source) {
        this.source.disconnect();
        this.source = null;
      }

      if (this.stream) {
        this.stream.getTracks().forEach(track => track.stop());
        this.stream = null;
      }

      if (this.context) {
        const context = this.context;
        this.context = null;
        if (context.state !== "closed") {
          await context.close();
        }
      }
    }
  }

  window.MyAIStudioLiveVoice = LiveVoice;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-u63-live-voice]").forEach(element => {
      element._u63VoiceInstance = new LiveVoice(element);
    });
  });
})();
