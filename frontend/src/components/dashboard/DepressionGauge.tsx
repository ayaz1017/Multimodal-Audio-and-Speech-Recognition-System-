import { useStore } from "../../store/useStore";

export const DepressionGauge = () => {
  const frames = useStore((state) => state.frames);
  const latestFrame = frames[frames.length - 1];
  
  const score = latestFrame ? latestFrame.depression_score : 0;
  const category = latestFrame ? latestFrame.depression_category : "Normal";
  
  // Calculate SVG arc parameters
  const getStrokeColor = (val: number) => {
    if (val < 25) return "#10B981"; // Emerald
    if (val < 50) return "#F59E0B"; // Amber
    if (val < 75) return "#F97316"; // Orange
    return "#EF4444"; // Red
  };

  const strokeDasharray = 283; // Circumference of r=45
  const strokeDashoffset = strokeDasharray - (strokeDasharray * score) / 100;

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative w-48 h-48">
        {/* Background Track */}
        <svg className="w-full h-full transform -rotate-90">
          <circle
            cx="96"
            cy="96"
            r="45"
            stroke="currentColor"
            strokeWidth="8"
            fill="transparent"
            className="text-white/5"
          />
          {/* Progress Indicator */}
          <circle
            cx="96"
            cy="96"
            r="45"
            stroke={getStrokeColor(score)}
            strokeWidth="8"
            fill="transparent"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-500 ease-out drop-shadow-md"
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold tracking-tighter text-white">
            {score.toFixed(0)}
          </span>
          <span className="text-sm font-medium text-slate-400 uppercase tracking-widest mt-1" style={{ color: getStrokeColor(score) }}>
            {category}
          </span>
        </div>
      </div>
      <div className="text-xs text-slate-500 text-center mt-2 max-w-[150px]">
        Continuous algorithmic risk estimation
      </div>
    </div>
  );
};
