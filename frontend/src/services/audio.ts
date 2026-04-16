import { wsService } from "./websocket";

export class AudioStreamer {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private mediaSource: MediaStreamAudioSourceNode | null = null;
  private recording: boolean = false;

  async startStream() {
    try {
      // Disable destructive browser filters: The AI needs raw acoustic data 
      // (sighs, breathiness, tremors) which Chrome often destroys as 'noise'.
      this.stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 16000
        } 
      });

      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      });

      // Verification of sample rate - some browsers may ignore the constraint
      console.log(`AudioContext Sample Rate: ${this.audioContext.sampleRate}`);

      this.mediaSource = this.audioContext.createMediaStreamSource(this.stream);
      
      // Using a larger buffer for more stable transmission
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

      this.processor.onaudioprocess = (e) => {
        if (!this.recording) return;

        const inputData = e.inputBuffer.getChannelData(0);
        const len = inputData.length;
        const pcm16 = new Int16Array(len);
        
        // Fast float-to-int16 conversion
        for (let i = 0; i < len; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Send binary buffer directly
        wsService.send(pcm16.buffer);
      };

      this.mediaSource.connect(this.processor);
      this.processor.connect(this.audioContext.destination);
      this.recording = true;
      return true;
    } catch (err) {
      console.error("Microphone access denied:", err);
      return false;
    }
  }

  stopStream() {
    this.recording = false;
    if (this.processor && this.audioContext) {
      this.processor.disconnect();
      this.mediaSource?.disconnect();
      this.audioContext.close();
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
    }
    this.audioContext = null;
    this.processor = null;
    this.mediaSource = null;
    this.stream = null;
  }
}

export const audioStreamer = new AudioStreamer();
