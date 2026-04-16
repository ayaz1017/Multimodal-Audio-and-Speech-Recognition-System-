import { useEffect, useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Mic, MicOff, AlertCircle, Users, Check, Wifi, Loader2, Activity, BarChart2, ShieldCheck, ShieldAlert, Save, MessageSquare } from "lucide-react";
import { useStore } from "../store/useStore";
import { audioStreamer } from "../services/audio";
import { wsService } from "../services/websocket";
import { api } from "../services/api";

import { EmotionChart } from "../components/dashboard/EmotionChart.tsx";
import { DepressionGauge } from "../components/dashboard/DepressionGauge.tsx";
import { VoiceOscilloscope } from "../components/dashboard/VoiceOscilloscope.tsx";
import { EmotionRadar } from "../components/dashboard/EmotionRadar.tsx";
import { EmotionDistributionBar } from "../components/dashboard/EmotionDistributionBar.tsx";

const BiomarkerBar = ({ label, value, color, active }: { label: string, value: number, color: string, active: boolean }) => (
  <div className={`space-y-1.5 transition-opacity duration-300 ${active ? 'opacity-100' : 'opacity-40'}`}>
    <div className="flex justify-between items-center text-[10px] uppercase tracking-wider font-bold text-slate-400">
      <span>{label}</span>
      <span className="font-mono">{Math.round(value)}%</span>
    </div>
    <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
      <div 
        className={`h-full ${color} transition-all duration-500 ease-out shadow-[0_0_8px_rgba(255,255,255,0.2)]`} 
        style={{ width: `${value}%` }}
      />
    </div>
  </div>
);

export const Dashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { token, sessionActive, setSessionActive, addFrame, clearFrames, frames } = useStore();
  const [error, setError] = useState("");
  const [patients, setPatients] = useState<any[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>(location.state?.selectedPatientId || "");
  const [showPatientSelect, setShowPatientSelect] = useState(false);
  const [wsStatus, setWsStatus] = useState<"connected" | "disconnected" | "error" | "connecting">("disconnected");
  const [isInitializing, setIsInitializing] = useState(false);
  const [lastAnalysisTime, setLastAnalysisTime] = useState<number | null>(null);
  const [swappedSpeakers, setSwappedSpeakers] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [transcript, setTranscript] = useState<string>("");
  const connectionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const latestFrame = frames[frames.length - 1];

  useEffect(() => {
    const unsub = wsService.onMessage((msg: any) => {
      if (msg.type === "analysis_result") {
        addFrame(msg);
        setLastAnalysisTime(Date.now());
        if (msg.transcript && msg.transcript.trim()) {
          setTranscript(msg.transcript.trim());
        }
      } else if (msg.type === "connection_status" || msg.type === "status") {
        const status = msg.status;
        if (status === "initializing") {
          setIsInitializing(true);
          return;
        }
        
        setWsStatus(status);
        if (status === 'connected') {
          setIsInitializing(false);
          if (connectionTimeoutRef.current) {
            clearTimeout(connectionTimeoutRef.current);
            connectionTimeoutRef.current = null;
          }
          // If we are connecting and demo mode is set, sync it immediately
          if (demoMode) {
            wsService.send({ action: "set_demo_mode", enabled: true });
          }
        }
        if (status === "error" || status === "disconnected") {
             setIsInitializing(false);
             setError(msg.message || "Session connection error.");
             if (connectionTimeoutRef.current) clearTimeout(connectionTimeoutRef.current);
        }
      }
    });

    api.get("/patients").then(res => {
      const patientList = res.data.patients;
      setPatients(patientList);
      if (location.state?.selectedPatientId) {
          setSelectedPatientId(location.state.selectedPatientId);
      } else if (patientList.length > 0 && !selectedPatientId) {
        setSelectedPatientId(patientList[0].id);
      }
    }).catch(err => {
      console.error("Failed to load patients", err);
      if (err.response?.status === 401) {
        setError("Your session has expired. Redirecting to login...");
        setTimeout(() => {
          localStorage.removeItem("token");
          navigate("/login");
        }, 2000);
      } else {
        setError("Database connection failed. Please ensure backend is running.");
      }
    });

    return unsub;
  }, [addFrame, selectedPatientId, demoMode]);

  const toggleDemoMode = () => {
    const nextValue = !demoMode;
    setDemoMode(nextValue);
    if (sessionActive && wsStatus === 'connected') {
      wsService.send({ action: "set_demo_mode", enabled: nextValue });
    }
  };

  const handleToggleRec = async () => {
    setError("");
    if (sessionActive) {
      audioStreamer.stopStream();
      wsService.disconnect();
      setSessionActive(false);
      setWsStatus("disconnected");
    } else {
      if (!selectedPatientId) {
        setError("Please select a patient first.");
        return;
      }

      try {
        setWsStatus("connecting");
        clearFrames();
        
        connectionTimeoutRef.current = setTimeout(() => {
          if (wsStatus === 'connecting') {
            setError("AI Engine is taking longer than expected to warm up. Please wait or try again.");
            setWsStatus("disconnected");
          }
        }, 30000);

        const res = await api.post("/sessions", {
          patient_id: selectedPatientId,
          notes: "Live analysis session"
        });
        const sessionId = res.data.id;
        
        wsService.connect(sessionId, token as string);
        const micStarted = await audioStreamer.startStream();
        if (micStarted) {
          setSessionActive(true, sessionId);
        } else {
          if (connectionTimeoutRef.current) clearTimeout(connectionTimeoutRef.current);
          setError("Microphone access denied.");
          setWsStatus("disconnected");
          wsService.disconnect();
        }
      } catch (err: any) {
        if (connectionTimeoutRef.current) clearTimeout(connectionTimeoutRef.current);
        console.error(err);
        setError("Failed to start session. Check your connection.");
        setWsStatus("disconnected");
      }
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!selectedPatientId) {
      setError("Please select a patient first.");
      return;
    }
    
    setIsUploading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patient_id", selectedPatientId);

    try {
      await api.post("/sessions/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      navigate("/sessions");
    } catch (err) {
      console.error(err);
      setError("Failed to analyze file. Please try a valid mp3/wav.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSaveSession = async () => {
    if (!sessionActive) return;
    
    setIsSaving(true);
    try {
      // 1. Stop audio and disconnect (this triggers backend merge/save)
      audioStreamer.stopStream();
      wsService.send({ action: "end" });
      wsService.disconnect();
      setSessionActive(false);
      
      // 2. Short delay to ensure backend has finalized the file
      setTimeout(() => {
        setIsSaving(false);
        navigate("/sessions");
      }, 1500);
      
    } catch (err) {
      console.error("Save failed", err);
      setIsSaving(false);
      setError("Failed to finalize session. It may still be available in History.");
    }
  };

  const selectedPatient = patients.find(p => p.id === selectedPatientId);

  return (
    <div className="h-full flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Active Analytics</h1>
            <p className="text-slate-400 mt-1">Real-time psychiatric biomarker detection engine.</p>
          </div>
          {sessionActive && (
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-bold tracking-widest uppercase transition-all ${
                wsStatus === 'connected' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
            }`}>
              {wsStatus === 'connected' ? <Wifi size={12}/> : <Loader2 size={12} className="animate-spin" />}
              {wsStatus === 'connected' ? 'Streaming' : 'Connecting'}
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={toggleDemoMode}
            className={`flex items-center gap-2 px-4 py-3 rounded-xl border transition-all shadow-xl group ${
              demoMode 
              ? "bg-amber-500/10 border-amber-500/30 text-amber-400" 
              : "bg-white/5 border-white/5 text-slate-400 hover:text-white"
            }`}
            title="Force Patient Identification for testing"
          >
            {demoMode ? <ShieldCheck size={16}/> : <ShieldAlert size={16}/>}
            <span className="text-sm font-medium">{demoMode ? "Demo Mode: ON" : "Demo Mode: OFF"}</span>
          </button>

          {!sessionActive && (
            <div className="relative">
              <button 
                onClick={() => setShowPatientSelect(!showPatientSelect)}
                className="flex items-center gap-2 bg-surface border border-white/5 px-4 py-3 rounded-xl text-slate-300 hover:text-white transition-all shadow-xl"
              >
                <Users size={16} />
                {selectedPatient ? selectedPatient.full_name : "Select Patient"}
              </button>
              
              {showPatientSelect && (
                <div className="absolute top-full right-0 mt-2 w-64 bg-surface border border-white/10 rounded-xl shadow-2xl z-50 py-2 overflow-hidden animate-in fade-in slide-in-from-top-2">
                  <div className="px-4 py-2 text-[10px] uppercase tracking-widest text-slate-500 font-bold border-b border-white/5 mb-2">My Patients</div>
                  {patients.length === 0 ? (
                    <div className="px-4 py-3 text-sm text-slate-500 italic">No patients found</div>
                  ) : (
                    patients.map(p => (
                      <button
                        key={p.id}
                        onClick={() => { setSelectedPatientId(p.id); setShowPatientSelect(false); }}
                        className="w-full text-left px-4 py-3 text-sm hover:bg-primary/10 hover:text-primary transition-colors flex items-center justify-between rounded-lg mx-1 w-[calc(100%-8px)]"
                      >
                        {p.full_name}
                        {selectedPatientId === p.id && <Check size={14} />}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {error && (
            <span className="flex items-center gap-2 text-red-400 text-xs bg-red-400/10 px-3 py-2 rounded-lg border border-red-400/20">
              <AlertCircle size={14}/> {error}
            </span>
          )}

          {sessionActive && (
            <button 
              onClick={handleSaveSession}
              disabled={isSaving}
              className="flex items-center gap-2 px-5 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 transition-all shadow-lg font-medium group"
            >
              {isSaving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} className="group-hover:scale-110 transition-transform" />}
              {isSaving ? "Saving..." : "Save Session"}
            </button>
          )}
          
          <button 
            onClick={handleToggleRec}
            disabled={(!selectedPatientId && !sessionActive) || wsStatus === 'connecting' || isSaving}
            className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all shadow-lg transform active:scale-95 ${
              sessionActive 
              ? "bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20" 
              : "bg-primary text-white hover:bg-primary/90 shadow-primary/20"
            } ${((!selectedPatientId && !sessionActive) || wsStatus === 'connecting' || isSaving) ? "cursor-not-allowed grayscale pointer-events-none" : ""}`}
            title={sessionActive ? "Stop recording without saving" : "Begin Analysis"}
          >
            {wsStatus === 'connecting' ? <Loader2 size={18} className="animate-spin" /> : (sessionActive ? <MicOff size={18} /> : <Mic size={18} />)}
            {wsStatus === 'connecting' 
              ? (isInitializing ? "Warming Up AI..." : "Preparing Session...") 
              : (sessionActive ? "Stop" : "Begin Recording")}
          </button>

          {!sessionActive && (
            <>
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileUpload} 
                accept="audio/mp3,audio/wav,audio/mpeg,audio/x-m4a,audio/*" 
                className="hidden" 
              />
              <button 
                onClick={() => fileInputRef.current?.click()}
                disabled={!selectedPatientId || isUploading}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all shadow-lg border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700 ${(!selectedPatientId || isUploading) ? "cursor-not-allowed opacity-50" : "transform active:scale-95"}`}
              >
                {isUploading ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                {isUploading ? "Analyzing..." : "Direct File Analysis"}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6 flex-1 min-h-0">

        {/* ── Left Column: Oscilloscope + Charts ──────────────────── */}
        <div className="col-span-8 flex flex-col gap-4 min-h-0">
          <VoiceOscilloscope
            energy={latestFrame?.live_metrics?.energy || 0}
            active={sessionActive && (demoMode || latestFrame?.speaker === 'patient')}
          />

          {/* Live Transcript Strip */}
          {transcript && sessionActive && (
            <div className="flex items-start gap-3 px-4 py-3 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-sm text-slate-300 animate-pulse-once">
              <MessageSquare size={15} className="text-indigo-400 mt-0.5 flex-shrink-0" />
              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] uppercase tracking-widest text-indigo-400 font-bold">Patient Said</span>
                <span className="italic text-slate-200 leading-relaxed">&ldquo;{transcript}&rdquo;</span>
              </div>
            </div>
          )}

          {/* 3-Chart Row */}
          <div className="grid grid-cols-3 gap-4 flex-1 min-h-0" style={{ minHeight: "260px" }}>
            <div className="col-span-2 bg-surface/30 border border-white/5 backdrop-blur-3xl rounded-3xl p-5 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-slate-300 font-medium text-sm flex items-center gap-2">
                  <Activity size={14} className="text-primary"/>
                  8-Emotion Timeline
                </h3>
                <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                  <span className={`w-1.5 h-1.5 rounded-full ${sessionActive ? 'bg-red-500 animate-pulse' : 'bg-slate-700'}`}/>
                  {sessionActive ? 'LIVE' : 'OFFLINE'}
                </div>
              </div>
              <div className="flex-1" style={{ minHeight: "200px" }}>
                <EmotionChart />
              </div>
            </div>
            <div className="bg-surface/30 border border-white/5 backdrop-blur-3xl rounded-3xl p-5 flex flex-col">
              <h3 className="text-slate-300 font-medium text-sm flex items-center gap-2 mb-1">
                <BarChart2 size={14} className="text-accent"/>
                Emotion Radar
              </h3>
              <div className="flex-1">
                <EmotionRadar />
              </div>
            </div>
          </div>

          {/* Session Frequency Bar */}
          <div className="bg-surface/30 border border-white/5 backdrop-blur-3xl rounded-3xl p-5" style={{ height: "140px" }}>
            <h3 className="text-slate-300 font-medium text-sm flex items-center gap-2 mb-2">
              <BarChart2 size={14} className="text-emerald-400"/>
              Session Emotion Frequency
            </h3>
            <div style={{ height: "85px" }}>
              <EmotionDistributionBar />
            </div>
          </div>
        </div>

        {/* ── Right Column: Risk + Biomarkers ─────────────────────── */}
        <div className="col-span-4 flex flex-col gap-6">
          <div className="bg-surface/30 border border-white/5 backdrop-blur-3xl rounded-3xl p-8 flex flex-col items-center shadow-2xl">
             <h3 className="text-slate-400 text-xs uppercase tracking-[0.2em] w-full text-center mb-6 font-bold">Risk Index</h3>
             <DepressionGauge />
          </div>

          <div className="flex-1 bg-surface/30 border border-white/5 backdrop-blur-3xl rounded-3xl p-6 shadow-2xl overflow-hidden relative">
             <h3 className="text-slate-300 font-medium mb-6 flex items-center gap-2">
                <BarChart2 size={16} className="text-emerald-400"/>
                Active Biomarkers
             </h3>
             <div className="space-y-4">
               {sessionActive && selectedPatient && (
                 <div className="bg-primary/5 rounded-2xl p-4 border border-primary/10 relative group overflow-hidden">
                   <div className="absolute inset-x-0 bottom-0 h-1 bg-primary/20 scale-x-0 group-hover:scale-x-100 transition-transform origin-left" />
                   <div className="text-xs text-primary/70 uppercase tracking-widest mb-1 font-bold">Identified Subject</div>
                   <div className="text-lg text-white font-bold">{selectedPatient.full_name}</div>
                   <div className="text-[10px] text-slate-500 font-mono mt-1 uppercase tracking-tighter">Verified Patient Record</div>
                 </div>
               )}
               
                <div className="bg-white/5 rounded-2xl p-4 border border-white/5 relative overflow-hidden group">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="text-xs text-slate-400 uppercase tracking-widest mb-1 font-bold">Voice Role</div>
                      <div className="text-xl text-primary font-bold capitalize">
                        {latestFrame 
                          ? (demoMode ? "Patient (Forced)" : (swappedSpeakers ? (latestFrame.speaker === 'patient' ? 'Doctor' : 'Patient') : latestFrame.speaker)) 
                          : (sessionActive ? "Sampling..." : "Idle")}
                      </div>
                    </div>
                    {sessionActive && !demoMode && (
                      <button 
                        onClick={() => setSwappedSpeakers(!swappedSpeakers)}
                        className="p-1 px-2 rounded-lg bg-white/5 hover:bg-white/10 text-[9px] text-slate-400 uppercase font-black border border-white/10 transition-colors"
                        title="Swap Patient/Doctor if AI misidentified"
                      >
                        Swap Labels
                      </button>
                    )}
                  </div>
                  
                  <div className="space-y-4 mt-6">
                    <BiomarkerBar 
                      label="Vocal Energy" 
                      value={latestFrame?.live_metrics?.energy || 0} 
                      color="bg-blue-400" 
                      active={latestFrame ? (demoMode || (swappedSpeakers ? latestFrame.speaker === 'doctor' : latestFrame.speaker === 'patient')) : false}
                    />
                    <BiomarkerBar 
                      label="Vocal Pitch" 
                      value={latestFrame?.live_metrics?.pitch || 0} 
                      color="bg-emerald-400" 
                      active={latestFrame ? (demoMode || (swappedSpeakers ? latestFrame.speaker === 'doctor' : latestFrame.speaker === 'patient')) : false}
                    />
                    <BiomarkerBar 
                      label="Vocal Tone" 
                      value={latestFrame?.live_metrics?.tone || 0} 
                      color="bg-amber-400" 
                      active={latestFrame ? (demoMode || (swappedSpeakers ? latestFrame.speaker === 'doctor' : latestFrame.speaker === 'patient')) : false}
                    />
                  </div>
                </div>

                {latestFrame && (demoMode || (swappedSpeakers ? latestFrame.speaker === 'doctor' : latestFrame.speaker === 'patient')) && (
                  <div className={`mt-2 rounded-2xl p-6 border transition-all duration-500 shadow-[0_0_20px_rgba(0,0,0,0.3)] ${
                    latestFrame.emotion.label === 'anger' ? 'bg-red-500/20 border-red-500/30' :
                    latestFrame.emotion.label === 'sad' ? 'bg-purple-500/20 border-purple-500/30' :
                    latestFrame.emotion.label === 'happy' ? 'bg-blue-500/20 border-blue-500/30' :
                    'bg-emerald-500/20 border-emerald-500/30'
                  }`}>
                    <div className="text-xs opacity-70 uppercase tracking-widest mb-1 font-bold">Detected Emotion</div>
                    <div className="flex items-center justify-between">
                      <div className="text-4xl font-black text-white uppercase tracking-tighter">
                        {latestFrame.emotion.label}
                      </div>
                      <div className="text-2xl font-mono text-white/50">
                        {Math.round(latestFrame.emotion.confidence * 100)}%
                      </div>
                    </div>
                  </div>
                )}
             </div>
             
             {lastAnalysisTime && sessionActive && (
                  <div className="absolute bottom-4 inset-x-6 text-[10px] text-slate-600 font-mono flex items-center justify-between">
                     <span>ASYNC_PIPELINE_OK</span>
                     <span>LAST_SYNC: {new Date(lastAnalysisTime).toLocaleTimeString()}</span>
                  </div>
              )}
          </div>
        </div>

      </div>
    </div>
  );
};
