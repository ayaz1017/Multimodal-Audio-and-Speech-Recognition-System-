import { ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip } from "recharts";
import { useStore } from "../../store/useStore";

const EMOTION_CONFIG: Record<string, string> = {
  calm:     "#22d3ee",
  happy:    "#22c55e",
  sad:      "#8b5cf6",
  anger:    "#ef4444",
  fear:     "#f97316",
  disgust:  "#a78bfa",
  surprise: "#f59e0b",
  neutral:  "#64748b",
};

const SESSION_EMOTIONS = ["calm", "happy", "sad", "anger", "fear", "disgust", "surprise", "neutral"];

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="bg-[#0f172a]/95 border border-white/10 rounded-xl p-2 text-xs shadow-xl">
      <span className="text-white font-bold capitalize">{item.payload.emotion}: </span>
      <span style={{ color: item.fill }}>{item.value.toFixed(1)}%</span>
    </div>
  );
};

export const EmotionDistributionBar = () => {
  const frames = useStore((state) => state.frames);

  // Count frequency of each emotion across all frames in the session
  const counts: Record<string, number> = {};
  SESSION_EMOTIONS.forEach(e => counts[e] = 0);
  frames.forEach(f => {
    const label = f.emotion?.label;
    if (label && counts[label] !== undefined) {
      counts[label]++;
    }
  });

  const total = frames.length || 1;
  const data = SESSION_EMOTIONS.map(e => ({
    emotion: e.charAt(0).toUpperCase() + e.slice(1),
    key: e,
    value: Math.round((counts[e] / total) * 100),
  })).filter(d => d.value > 0 || frames.length === 0);

  if (frames.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-xs italic">
        Awaiting session data...
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 10, left: 40, bottom: 0 }}>
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis
          type="category"
          dataKey="emotion"
          tick={{ fontSize: 10, fill: "#64748b", fontWeight: "bold" }}
          axisLine={false}
          tickLine={false}
          width={55}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {data.map((entry) => (
            <Cell key={entry.key} fill={EMOTION_CONFIG[entry.key] || "#64748b"} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};
