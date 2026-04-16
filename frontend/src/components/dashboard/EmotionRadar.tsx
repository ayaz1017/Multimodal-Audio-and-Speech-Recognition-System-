import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar } from "recharts";
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

export const EmotionRadar = () => {
  const frames = useStore((state) => state.frames);
  const latest = frames[frames.length - 1];

  const d = latest?.emotion?.distribution || {};

  const data = [
    { emotion: "Calm",     value: ((d.calm     ?? d.neutral    ?? 0) * 100) },
    { emotion: "Happy",    value: ((d.happy    ?? 0) * 100) },
    { emotion: "Sad",      value: ((d.sad      ?? 0) * 100) },
    { emotion: "Anger",    value: ((d.anger    ?? d.angry   ?? 0) * 100) },
    { emotion: "Fear",     value: ((d.fear     ?? d.fearful ?? 0) * 100) },
    { emotion: "Disgust",  value: ((d.disgust  ?? 0) * 100) },
    { emotion: "Surprise", value: ((d.surprise ?? d.surprised ?? 0) * 100) },
  ];

  const primaryEmotion = latest?.emotion?.label || "–";
  const primaryColor = EMOTION_CONFIG[primaryEmotion] || "#64748b";
  const confidence = Math.round((latest?.emotion?.confidence || 0) * 100);

  return (
    <div className="flex flex-col items-center w-full">
      <div className="w-full flex items-center justify-between mb-3">
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Detected Emotion</div>
          <div className="text-2xl font-black capitalize tracking-tighter" style={{ color: primaryColor }}>{primaryEmotion}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Confidence</div>
          <div className="text-2xl font-black font-mono" style={{ color: primaryColor }}>{confidence}%</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={data} margin={{ top: 0, right: 10, bottom: 0, left: 10 }}>
          <PolarGrid stroke="rgba(255,255,255,0.06)" />
          <PolarAngleAxis
            dataKey="emotion"
            tick={{ fontSize: 10, fill: "#64748b", fontWeight: "bold" }}
          />
          <Radar
            name="probability"
            dataKey="value"
            stroke={primaryColor}
            fill={primaryColor}
            fillOpacity={0.15}
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};
