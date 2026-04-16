import { useEffect, useRef, useState, useCallback } from "react";
import WaveSurfer from "wavesurfer.js";
import { Play, Pause, RotateCcw, Volume2, VolumeX, Loader2 } from "lucide-react";
import { useStore } from "../../store/useStore";

interface AudioReplayProps {
  sessionId: string;
  onTimeUpdate?: (time: number) => void;
}

export const AudioReplay = ({ sessionId, onTimeUpdate }: AudioReplayProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const token = useStore((state) => state.token);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [isMuted, setIsMuted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    if (!containerRef.current || !token) return;

    setIsLoading(true);
    setLoadError(false);

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "rgba(100, 116, 139, 0.4)",
      progressColor: "rgba(59, 130, 246, 0.9)",
      cursorColor: "#60A5FA",
      barWidth: 2,
      barGap: 1,
      barRadius: 3,
      cursorWidth: 2,
      height: 72,
      normalize: true,
      url: `http://localhost:8000/api/v1/audio/session/${sessionId}?token=${token}`,
    });

    ws.on("play", () => setIsPlaying(true));
    ws.on("pause", () => setIsPlaying(false));
    ws.on("timeupdate", (t) => {
      setCurrentTime(t);
      onTimeUpdate?.(t);
    });
    ws.on("ready", (d) => {
      setDuration(d);
      setIsLoading(false);
    });
    ws.on("error", () => {
      setIsLoading(false);
      setLoadError(true);
    });

    wavesurferRef.current = ws;
    ws.setVolume(volume);

    return () => ws.destroy();
  }, [sessionId]);

  const togglePlay = useCallback(() => wavesurferRef.current?.playPause(), []);
  const handleRestart = useCallback(() => {
    wavesurferRef.current?.setTime(0);
    wavesurferRef.current?.play();
  }, []);

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = parseFloat(e.target.value);
    setVolume(v);
    wavesurferRef.current?.setVolume(v);
    setIsMuted(v === 0);
  };

  const toggleMute = () => {
    const next = !isMuted;
    setIsMuted(next);
    wavesurferRef.current?.setVolume(next ? 0 : volume);
  };

  const formatTime = (time: number) => {
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="w-full space-y-4">
      {/* Waveform */}
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-surface/50 rounded-xl">
            <Loader2 className="animate-spin text-primary" size={24} />
          </div>
        )}
        {loadError && (
          <div className="flex items-center justify-center h-[72px] bg-white/5 rounded-xl text-slate-500 text-sm">
            Audio file unavailable or still processing.
          </div>
        )}
        <div
          ref={containerRef}
          className="w-full rounded-xl overflow-hidden bg-black/20"
          style={{ display: loadError ? "none" : "block" }}
        />
      </div>

      {/* Progress bar */}
      <div className="w-full h-0.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-primary to-accent transition-all duration-100"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <button
            onClick={handleRestart}
            className="w-9 h-9 rounded-full bg-white/5 text-slate-400 flex items-center justify-center hover:bg-white/10 hover:text-white transition-all border border-white/5"
          >
            <RotateCcw size={15} />
          </button>
          <button
            onClick={togglePlay}
            disabled={isLoading || loadError}
            className="w-12 h-12 rounded-full bg-primary text-white flex items-center justify-center hover:bg-blue-600 transition-all shadow-lg shadow-primary/30 disabled:opacity-40"
          >
            {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" className="ml-0.5" />}
          </button>
        </div>

        {/* Time */}
        <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
          <span className="text-white">{formatTime(currentTime)}</span>
          <span>/</span>
          <span>{formatTime(duration)}</span>
        </div>

        {/* Volume */}
        <div className="flex items-center gap-2 ml-auto">
          <button onClick={toggleMute} className="text-slate-500 hover:text-white transition-colors">
            {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={isMuted ? 0 : volume}
            onChange={handleVolumeChange}
            className="w-20 accent-primary cursor-pointer"
          />
        </div>
      </div>
    </div>
  );
};
