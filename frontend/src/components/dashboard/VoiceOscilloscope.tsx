import { useEffect, useRef } from "react";

interface VoiceOscilloscopeProps {
  energy: number; // 0-100
  active: boolean;
  color?: string;
}

export const VoiceOscilloscope = ({ energy, active, color = "#10b981" }: VoiceOscilloscopeProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dataPoints = useRef<number[]>(new Array(100).fill(0));
  const animationRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = () => {
      // Shift data points and add new value
      // If not active, we add a very small jitter or 0
      const nextValue = active ? (energy / 100) * canvas.height * 0.8 : Math.random() * 2;
      dataPoints.current.push(nextValue);
      dataPoints.current.shift();

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw background grid
      ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
      ctx.lineWidth = 1;
      for (let i = 0; i < canvas.width; i += 40) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, canvas.height);
        ctx.stroke();
      }
      for (let i = 0; i < canvas.height; i += 20) {
        ctx.beginPath();
        ctx.moveTo(0, i);
        ctx.lineTo(canvas.width, i);
        ctx.stroke();
      }

      // Draw wave
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.shadowBlur = 10;
      ctx.shadowColor = color;

      const step = canvas.width / (dataPoints.current.length - 1);
      
      dataPoints.current.forEach((point, i) => {
        const x = i * step;
        const y = canvas.height / 2 - point / 2 + Math.sin(Date.now() / 100 + i) * (active ? 2 : 0);
        
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });

      ctx.stroke();
      ctx.shadowBlur = 0;

      animationRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [energy, active, color]);

  return (
    <div className="w-full h-24 bg-black/20 rounded-2xl overflow-hidden border border-white/5 relative group">
      <div className="absolute top-2 left-4 text-[9px] uppercase tracking-widest font-bold text-slate-500 z-10">
        Voice Fluctuations (SENS_HIGH)
      </div>
      <canvas 
        ref={canvasRef} 
        width={600} 
        height={96} 
        className="w-full h-full opacity-80 group-hover:opacity-100 transition-opacity"
      />
      {!active && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/10 backdrop-blur-[1px]">
          <span className="text-[10px] text-slate-600 font-mono uppercase tracking-tighter">Waiting for Voice Flux...</span>
        </div>
      )}
    </div>
  );
};
