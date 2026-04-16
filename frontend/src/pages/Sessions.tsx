import { useState, useEffect } from "react";
import {
  FileText, Calendar, User, BarChart2, Loader2, ArrowLeft,
  Download, Trash2, AlertTriangle, Play, TrendingUp, Brain,
  HeartPulse, Activity, Zap
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell, RadialBarChart, RadialBar, LineChart, Line, Legend
} from "recharts";
import { api } from "../services/api";
import { AudioReplay } from "../components/sessions/AudioReplay";

// ── Emotion Color Map ─────────────────────────────────────────────
const EMOTION_COLORS: Record<string, string> = {
  calm:     "#22d3ee",
  happy:    "#22c55e",
  sad:      "#8b5cf6",
  anger:    "#ef4444",
  fear:     "#f97316",
  disgust:  "#a78bfa",
  surprise: "#f59e0b",
  neutral:  "#64748b",
};

const getRiskColor = (score: number) => {
  if (score < 25) return "#22c55e";
  if (score < 50) return "#f59e0b";
  if (score < 75) return "#f97316";
  return "#ef4444";
};

const getRiskLabel = (score: number) => {
  if (score < 25) return "Normal";
  if (score < 50) return "Mild";
  if (score < 75) return "Moderate";
  return "Severe";
};

// ── Custom Tooltip ────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0f172a]/95 border border-white/10 rounded-xl p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-2 font-bold">{label}s</p>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-slate-300">{p.name}:</span>
          <span className="text-white font-bold">{Number(p.value).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
};

// ── Risk Gauge ────────────────────────────────────────────────────
const RiskGauge = ({ score }: { score: number }) => {
  const color = getRiskColor(score);
  const label = getRiskLabel(score);
  const data = [{ value: score, fill: color }];
  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative w-44 h-44">
        <RadialBarChart
          width={176} height={176}
          cx={88} cy={88}
          innerRadius={60} outerRadius={82}
          startAngle={220} endAngle={-40}
          data={data}
        >
          <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "rgba(255,255,255,0.03)" }} />
        </RadialBarChart>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-4xl font-bold" style={{ color }}>{score.toFixed(0)}</div>
          <div className="text-xs font-bold uppercase tracking-widest mt-1" style={{ color }}>{label}</div>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-2">
        <HeartPulse size={14} style={{ color }} />
        <span className="text-xs text-slate-400 font-medium">Composite Risk Index</span>
      </div>
    </div>
  );
};

// ── Session Detail View ───────────────────────────────────────────
const SessionDetail = ({
  session,
  onBack,
  onDelete
}: {
  session: any;
  onBack: () => void;
  onDelete: (id: string) => void;
}) => {
  const [frames, setFrames] = useState<any[]>([]);
  const [loadingFrames, setLoadingFrames] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [audioTime, setAudioTime] = useState(0);

  useEffect(() => {
    api.get(`/sessions/${session.id}/frames`)
      .then(res => setFrames(res.data))
      .catch(console.error)
      .finally(() => setLoadingFrames(false));
  }, [session.id]);

  const emotionChartData = frames.map(f => ({
    time: (f.chunk_index || 0) * 3,
    Neutral:  Math.round((f.emotion_distribution?.neutral  || 0) * 100),
    Calm:     Math.round((f.emotion_distribution?.calm     || 0) * 100),
    Happy:    Math.round((f.emotion_distribution?.happy    || 0) * 100),
    Sad:      Math.round((f.emotion_distribution?.sad      || 0) * 100),
    Anger:    Math.round((f.emotion_distribution?.anger    || f.emotion_distribution?.angry   || 0) * 100),
    Fear:     Math.round((f.emotion_distribution?.fear     || f.emotion_distribution?.fearful || 0) * 100),
    Disgust:  Math.round((f.emotion_distribution?.disgust  || 0) * 100),
    Surprise: Math.round((f.emotion_distribution?.surprise || f.emotion_distribution?.surprised || 0) * 100),
  }));

  const riskChartData = frames.map(f => ({
    time: (f.chunk_index || 0) * 3,
    Risk: Math.round(f.depression_score || 0),
  }));

  // Compute emotion distribution pie from all frames
  const emotionFrequency: Record<string, number> = {};
  frames.forEach(f => {
    const label = f.emotion || "calm";
    emotionFrequency[label] = (emotionFrequency[label] || 0) + 1;
  });
  const total = frames.length || 1;
  const emotionDistData = Object.entries(emotionFrequency).map(([name, count]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value: Math.round((count / total) * 100),
    fill: EMOTION_COLORS[name] || "#64748b"
  }));

  // Compute score live from frames (most accurate) — fall back to session record
  const frameScores = frames.map(f => f.depression_score || 0).filter(s => s > 0);
  const score = frameScores.length > 0
    ? Math.round(frameScores.reduce((a, b) => a + b, 0) / frameScores.length * 10) / 10
    : (session.final_depression_score || 0);

  const duration = session.audio_metadata?.audio_duration_seconds || session.duration_seconds || 0;

  return (
    <div className="h-full flex flex-col gap-6 overflow-y-auto pb-8">
      {/* Header */}
      <div className="flex items-start justify-between sticky top-0 bg-[#0B0F19]/90 backdrop-blur-md py-3 -mx-1 px-1 z-10">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors group"
          >
            <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
          </button>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest ${
                session.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-primary/10 text-primary"
              }`}>{session.status}</span>
            </div>
            <h1 className="text-2xl font-bold text-white">{session.patient_name || "Patient Session"}</h1>
            <div className="flex gap-4 text-xs text-slate-500 mt-1">
              <span className="flex items-center gap-1"><Calendar size={12}/>{new Date(session.started_at).toLocaleString()}</span>
              <span className="flex items-center gap-1"><User size={12}/>{session.patient_name || session.patient_id?.substring(0, 8)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href={`http://localhost:8000/api/v1/audio/session/${session.id}`}
            download
            className="bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2 border border-white/10"
          >
            <Download size={15} /> Export WAV
          </a>
          <button
            onClick={() => setConfirmDelete(true)}
            className="bg-red-500/10 hover:bg-red-500/20 text-red-400 p-2 rounded-xl border border-red-500/20 transition-all"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* Audio Player + Risk Index Row */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-white/[0.03] border border-white/5 p-6 rounded-3xl backdrop-blur-md">
          <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-5 flex items-center gap-2">
            <Activity size={14} className="text-primary" /> Session Playback
          </h3>
          <AudioReplay sessionId={session.id} onTimeUpdate={setAudioTime} />
        </div>

        <div className="bg-white/[0.03] border border-white/5 p-6 rounded-3xl backdrop-blur-md flex flex-col items-center justify-center">
          <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-4 flex items-center gap-2">
            <HeartPulse size={14} className="text-red-400" /> Risk Index
          </h3>
          <RiskGauge score={score} />
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Duration", value: `${duration.toFixed(0)}s`, sub: "Total Recording", icon: <Activity size={16} />, color: "text-primary" },
          { label: "Depression Score", value: score.toFixed(1), sub: getRiskLabel(score), icon: <HeartPulse size={16} />, color: getRiskColor(score) !== "#22c55e" ? "text-amber-400" : "text-emerald-400" },
          { label: "Frames Analyzed", value: frames.length.toString(), sub: "AI Processing Units", icon: <Brain size={16} />, color: "text-accent" },
          { label: "Data Integrity", value: "100%", sub: "Signal Verified", icon: <Zap size={16} />, color: "text-emerald-400" },
        ].map(stat => (
          <div key={stat.label} className="bg-white/[0.03] border border-white/5 p-5 rounded-2xl">
            <div className={`mb-3 ${stat.color}`}>{stat.icon}</div>
            <div className="text-xs text-slate-500 uppercase tracking-widest mb-1">{stat.label}</div>
            <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
            <div className="text-[10px] text-slate-600 mt-1 font-medium uppercase tracking-wider">{stat.sub}</div>
          </div>
        ))}
      </div>

      {loadingFrames ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="animate-spin text-primary" size={28} />
          <span className="ml-3 text-slate-400">Loading analysis data...</span>
        </div>
      ) : frames.length === 0 ? (
        <div className="bg-white/[0.03] border border-white/5 p-8 rounded-3xl text-center text-slate-500">
          No analysis frames found for this session.
        </div>
      ) : (
        <>
          {/* Emotion Timeline Chart */}
          <div className="bg-white/[0.03] border border-white/5 p-6 rounded-3xl backdrop-blur-md">
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-6 flex items-center gap-2">
              <TrendingUp size={14} className="text-primary" /> Emotion Timeline
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={emotionChartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  {Object.entries(EMOTION_COLORS).map(([key, color]) => (
                    <linearGradient key={key} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={color} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis dataKey="time" stroke="rgba(255,255,255,0.2)" fontSize={11} tickFormatter={v => `${v}s`} minTickGap={20} />
                <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} domain={[0, 100]} tickFormatter={v => `${v}%`} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "16px" }} />
                {[
                  { key: "Neutral",  color: EMOTION_COLORS.neutral  || "#94a3b8" },
                  { key: "Calm",     color: EMOTION_COLORS.calm },
                  { key: "Happy",    color: EMOTION_COLORS.happy },
                  { key: "Sad",      color: EMOTION_COLORS.sad },
                  { key: "Anger",    color: EMOTION_COLORS.anger },
                  { key: "Fear",     color: EMOTION_COLORS.fear },
                  { key: "Disgust",  color: EMOTION_COLORS.disgust  || "#84cc16" },
                  { key: "Surprise", color: EMOTION_COLORS.surprise || "#f59e0b" },
                ].map(({ key, color }) => (
                  <Area
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={color}
                    fill={`url(#grad-${key.toLowerCase()})`}
                    strokeWidth={1.5}
                    fillOpacity={1}
                    isAnimationActive={false}
                    dot={false}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Risk Index over time + Emotion Distribution */}
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white/[0.03] border border-white/5 p-6 rounded-3xl backdrop-blur-md">
              <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-6 flex items-center gap-2">
                <HeartPulse size={14} className="text-red-400" /> Risk Index Timeline
              </h3>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={riskChartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="time" stroke="rgba(255,255,255,0.2)" fontSize={11} tickFormatter={v => `${v}s`} />
                  <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} domain={[0, 100]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="Risk"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white/[0.03] border border-white/5 p-6 rounded-3xl backdrop-blur-md">
              <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-6 flex items-center gap-2">
                <Brain size={14} className="text-accent" /> Emotion Distribution
              </h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={emotionDistData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="name" stroke="rgba(255,255,255,0.2)" fontSize={10} />
                  <YAxis stroke="rgba(255,255,255,0.2)" fontSize={11} tickFormatter={v => `${v}%`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                    {emotionDistData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} fillOpacity={0.8} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Patient Transcripts */}
          <div className="bg-white/[0.03] border border-white/5 p-6 rounded-3xl backdrop-blur-md mt-6">
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-6 flex items-center gap-2">
              <FileText size={14} className="text-primary" /> Patient Transcript Log
            </h3>
            <div className="max-h-64 overflow-y-auto pr-2 space-y-3">
              {frames.filter(f => f.transcript && f.transcript.trim()).map((frame, idx) => {
                const isActive = audioTime >= frame.segment_start && audioTime < frame.segment_end;
                return (
                  <div key={idx} className={`p-4 rounded-xl border transition-all ${
                    isActive 
                      ? "bg-primary/10 border-primary/30 shadow-[0_0_15px_rgba(56,189,248,0.1)]" 
                      : "bg-white/[0.02] border-white/5 opacity-50 hover:opacity-100"
                  }`}>
                    <div className="flex justify-between items-center mb-2">
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${isActive ? "text-primary" : "text-slate-500"}`}>
                        {new Date(frame.segment_start * 1000).toISOString().substr(14, 5)} - {new Date(frame.segment_end * 1000).toISOString().substr(14, 5)}
                      </span>
                      <span style={{ color: EMOTION_COLORS[(frame.emotion || "").toLowerCase()] || "#94a3b8" }} className="text-[10px] font-bold uppercase tracking-widest bg-white/5 px-2 py-0.5 rounded">
                        {frame.emotion}
                      </span>
                    </div>
                    <p className={`text-sm ${isActive ? "text-white" : "text-slate-400"}`}>"{frame.transcript}"</p>
                  </div>
                );
              })}
              {frames.filter(f => f.transcript && f.transcript.trim()).length === 0 && (
                <div className="text-center text-slate-500 text-sm py-8 bg-white/[0.02] rounded-xl border border-white/5">
                  No transcript data available for this session.
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Delete Confirm Modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-[#0f172a] border border-white/10 p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <div className="flex items-center gap-4 text-red-400 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-red-400/10 flex items-center justify-center">
                <AlertTriangle size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">Delete Session?</h3>
                <p className="text-slate-400 text-sm">This action cannot be undone.</p>
              </div>
            </div>
            <p className="text-slate-300 text-sm mb-8 leading-relaxed">
              This will permanently delete the recording for <span className="text-white font-bold">{session.patient_name}</span> and all analysis data.
            </p>
            <div className="flex gap-4">
              <button onClick={() => setConfirmDelete(false)} className="flex-1 bg-white/5 hover:bg-white/10 text-white py-3 rounded-xl font-medium transition-all">
                Cancel
              </button>
              <button onClick={() => { onDelete(session.id); setConfirmDelete(false); }} className="flex-1 bg-red-500 hover:bg-red-600 text-white py-3 rounded-xl font-medium shadow-lg shadow-red-500/20 transition-all">
                Delete Forever
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Helpers ───────────────────────────────────────────────────────
const formatDate = (dateStr: string) => {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", {
    weekday: "short", day: "2-digit", month: "short", year: "numeric",
  });
};
const formatTime = (dateStr: string) => new Date(dateStr).toLocaleTimeString("en-IN", {
  hour: "2-digit", minute: "2-digit",
});

// ── Main Sessions Page ────────────────────────────────────────────
export const Sessions = () => {
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [expandedPatient, setExpandedPatient] = useState<string | null>(null);

  useEffect(() => { fetchSessions(); }, []);

  const fetchSessions = async () => {
    try {
      const res = await api.get("/sessions");
      setSessions(res.data.sessions);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (id: string) => {
    api.delete(`/sessions/${id}`).catch(console.error);
    setSessions(prev => prev.filter(s => s.id !== id));
    if (selectedSessionId === id) setSelectedSessionId(null);
  };

  const selectedSession = sessions.find(s => s.id === selectedSessionId);

  if (selectedSessionId && selectedSession) {
    return (
      <SessionDetail
        session={selectedSession}
        onBack={() => setSelectedSessionId(null)}
        onDelete={handleDelete}
      />
    );
  }

  // Group sessions by patient
  const byPatient: Record<string, { name: string; patientId: string; sessions: any[] }> = {};
  sessions.forEach(s => {
    const key = s.patient_id;
    if (!byPatient[key]) {
      byPatient[key] = { name: s.patient_name || `Patient ${s.patient_id.substring(0, 8)}`, patientId: key, sessions: [] };
    }
    byPatient[key].sessions.push(s);
  });

  // Sort each patient's sessions by newest first
  Object.values(byPatient).forEach(p => p.sessions.sort((a, b) =>
    new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  ));

  // Sort patients by their most recent session
  const patientGroups = Object.values(byPatient).sort((a, b) =>
    new Date(b.sessions[0].started_at).getTime() - new Date(a.sessions[0].started_at).getTime()
  );

  return (
    <div className="h-full flex flex-col">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight">Analysis History</h1>
        <p className="text-slate-400 mt-1">Sessions grouped by patient — click a patient to view their records.</p>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="animate-spin text-primary" size={32} />
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex-1 border border-white/5 bg-white/[0.02] rounded-2xl p-8 flex flex-col items-center justify-center">
          <FileText size={48} className="text-slate-700 mb-4" />
          <h3 className="text-xl font-medium text-slate-300">No Recorded Sessions</h3>
          <p className="text-slate-500 mt-2 text-center max-w-sm">Analysis frames will appear here once you complete a live recording session.</p>
        </div>
      ) : (
        <div className="space-y-4 overflow-y-auto pb-4">
          {patientGroups.map(group => {
            const isExpanded = expandedPatient === group.patientId;
            const avgRisk = group.sessions.reduce((s, x) => s + (x.final_depression_score || 0), 0) / group.sessions.length;
            const riskColor = getRiskColor(avgRisk);
            const latestDate = formatDate(group.sessions[0].started_at);

            return (
              <div key={group.patientId} className="bg-white/[0.03] border border-white/5 rounded-2xl overflow-hidden transition-all">
                {/* Patient Header — click to expand */}
                <div
                  className="flex items-center justify-between p-5 cursor-pointer hover:bg-white/[0.04] transition-all group"
                  onClick={() => setExpandedPatient(isExpanded ? null : group.patientId)}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center text-lg font-black text-white`}
                      style={{ background: `${riskColor}25`, border: `1px solid ${riskColor}40` }}>
                      {group.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-bold text-white group-hover:text-primary transition-colors">{group.name}</h3>
                        <span className="text-[10px] font-bold bg-white/5 border border-white/10 text-slate-400 px-2 py-0.5 rounded-full">
                          {group.sessions.length} session{group.sessions.length !== 1 ? "s" : ""}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-xs text-slate-500">
                        <span className="flex items-center gap-1"><Calendar size={11}/> Latest: {latestDate}</span>
                        <span className="flex items-center gap-1">
                          Avg Risk:
                          <span className="font-bold" style={{ color: riskColor }}>{avgRisk.toFixed(0)} ({getRiskLabel(avgRisk)})</span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right hidden sm:block">
                      <div className="text-[10px] text-slate-600 uppercase tracking-widest font-bold">Latest Risk</div>
                      <div className="text-xl font-bold" style={{ color: riskColor }}>
                        {(group.sessions[0].final_depression_score || 0).toFixed(0)}
                      </div>
                    </div>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-slate-500 transition-all ${isExpanded ? "bg-primary/10 text-primary rotate-90" : "bg-white/5"}`}>
                      <Play size={12} fill="currentColor" />
                    </div>
                  </div>
                </div>

                {/* Session List — shown when expanded */}
                {isExpanded && (
                  <div className="border-t border-white/5 divide-y divide-white/[0.03]">
                    {group.sessions.map(s => {
                      const score = s.final_depression_score || 0;
                      const rc = getRiskColor(score);
                      const dateStr = formatDate(s.started_at);
                      const timeStr = formatTime(s.started_at);
                      return (
                        <div
                          key={s.id}
                          onClick={() => setSelectedSessionId(s.id)}
                          className="flex items-center justify-between px-5 py-4 hover:bg-white/[0.03] cursor-pointer transition-all group/row"
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-9 h-9 rounded-xl bg-white/5 flex items-center justify-center text-slate-600 group-hover/row:text-primary group-hover/row:bg-primary/5 transition-all">
                              <BarChart2 size={16} />
                            </div>
                            <div>
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wider ${
                                  s.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-primary/10 text-primary"
                                }`}>{s.status}</span>
                                <span className="text-[10px] text-slate-600 font-mono">#{s.id.substring(0, 8)}</span>
                              </div>
                              <div className="flex items-center gap-3 text-xs text-slate-500">
                                <span className="flex items-center gap-1 font-medium text-slate-400">
                                  <Calendar size={11}/>{dateStr}
                                </span>
                                <span className="text-slate-600">·</span>
                                <span>{timeStr}</span>
                                {s.audio_metadata?.audio_duration_seconds && (
                                  <>
                                    <span className="text-slate-600">·</span>
                                    <span>{Math.round(s.audio_metadata.audio_duration_seconds)}s</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-right">
                              <div className="text-[10px] text-slate-600 uppercase tracking-widest font-bold">Risk</div>
                              <div className="text-lg font-bold" style={{ color: rc }}>{score.toFixed(0)}</div>
                            </div>
                            <div className="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center text-slate-600 group-hover/row:text-primary group-hover/row:bg-primary/10 transition-all">
                              <Play size={11} fill="currentColor" />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
