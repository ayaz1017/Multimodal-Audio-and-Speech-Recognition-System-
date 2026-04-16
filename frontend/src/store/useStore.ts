import { create } from 'zustand';

interface AnalysisFrame {
  chunk_index: number;
  speaker: string;
  emotion: {
    label: string;
    confidence: number;
    distribution: Record<string, number>;
  };
  depression_score: number;
  depression_category: string;
  depression_trend: string;
  rolling_depression_avg: number;
  features: {
    rms_energy: number;
    pitch_mean: number | null;
  };
  live_metrics?: {
    energy: number;
    pitch: number;
    tone: number;
  };
}

interface AppState {
  token: string | null;
  user: any | null;
  sessionActive: boolean;
  activeSessionId: string | null;
  frames: AnalysisFrame[];
  
  setToken: (token: string | null) => void;
  setUser: (user: any | null) => void;
  setSessionActive: (active: boolean, sessionId?: string) => void;
  addFrame: (frame: AnalysisFrame) => void;
  clearFrames: () => void;
  logout: () => void;
}

export const useStore = create<AppState>((set) => ({
  token: localStorage.getItem("token"),
  user: null,
  sessionActive: false,
  activeSessionId: null,
  frames: [],
  
  setToken: (token) => {
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
    set({ token });
  },
  setUser: (user) => set({ user }),
  setSessionActive: (active, sessionId) => set({ sessionActive: active, activeSessionId: sessionId || null }),
  addFrame: (frame) => set((state) => {
    // Keep last 100 frames to prevent memory bloat in live charts
    const newFrames = [...state.frames, frame];
    if (newFrames.length > 100) newFrames.shift();
    return { frames: newFrames };
  }),
  clearFrames: () => set({ frames: [] }),
  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null, sessionActive: false, activeSessionId: null, frames: [] });
  }
}));
