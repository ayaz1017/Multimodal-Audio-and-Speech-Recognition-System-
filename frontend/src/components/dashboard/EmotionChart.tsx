import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  CartesianGrid, Legend
} from "recharts";
import { useStore } from "../../store/useStore";

// Full 8-class RAVDESS emotion palette
const EMOTION_CONFIG: Record<string, { color: string; gradient: string }> = {
  calm:     { color: "#22d3ee", gradient: "calmGrad" },
  happy:    { color: "#22c55e", gradient: "happyGrad" },
  sad:      { color: "#8b5cf6", gradient: "sadGrad" },
  anger:    { color: "#ef4444", gradient: "angerGrad" },
  fear:     { color: "#f97316", gradient: "fearGrad" },
  disgust:  { color: "#a78bfa", gradient: "disgustGrad" },
  surprise: { color: "#f59e0b", gradient: "surpriseGrad" },
  neutral:  { color: "#64748b", gradient: "neutralGrad" },
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const top = [...payload].sort((a, b) => b.value - a.value).slice(0, 4);
  return (
    <div className="bg-[#0f172a]/95 border border-white/10 rounded-xl p-3 text-xs shadow-xl backdrop-blur-md">
      <p className="text-slate-400 mb-2 font-bold tracking-widest">{label}s</p>
      {top.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2 py-0.5">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-slate-300 capitalize">{p.name}:</span>
          <span className="text-white font-bold ml-auto">{Number(p.value).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
};

export const EmotionChart = () => {
  const frames = useStore((state) => state.frames);

  const data = frames.map((frame) => {
    const d = frame.emotion?.distribution || {};
    return {
      time: (frame.chunk_index || 0) * 3,
      calm:     (d.calm     ?? d.neutral ?? 0) * 100,
      happy:    (d.happy    ?? 0) * 100,
      sad:      (d.sad      ?? 0) * 100,
      anger:    (d.anger    ?? d.angry   ?? 0) * 100,
      fear:     (d.fear     ?? d.fearful ?? 0) * 100,
      disgust:  (d.disgust  ?? 0) * 100,
      surprise: (d.surprise ?? d.surprised ?? 0) * 100,
    };
  });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 5, right: 5, left: -22, bottom: 20 }}>
        <defs>
          {Object.entries(EMOTION_CONFIG).map(([key, { color, gradient }]) => (
            <linearGradient key={gradient} id={gradient} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.35} />
              <stop offset="95%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis
          dataKey="time"
          stroke="rgba(255,255,255,0.15)"
          fontSize={10}
          tickFormatter={(v) => `${v}s`}
          minTickGap={20}
          tick={{ fill: "#64748b" }}
        />
        <YAxis
          stroke="rgba(255,255,255,0.15)"
          fontSize={10}
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
          tick={{ fill: "#64748b" }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: "10px", paddingTop: "8px" }}
          formatter={(value) => <span style={{ color: EMOTION_CONFIG[value]?.color, textTransform: "capitalize", fontWeight: "bold" }}>{value}</span>}
        />
        {Object.entries(EMOTION_CONFIG).map(([key, { color, gradient }]) => (
          <Area
            key={key}
            type="monotone"
            dataKey={key}
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${gradient})`}
            fillOpacity={1}
            isAnimationActive={false}
            dot={false}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
};
