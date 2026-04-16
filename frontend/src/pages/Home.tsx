import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Brain, Ear, ShieldCheck, BarChart3, ArrowRight, Play, HeartPulse, Sparkles, X, ChevronLeft, ChevronRight } from "lucide-react";

// ── Demo Slideshow Modal ──────────────────────────────────────────
const DEMO_SLIDES = [
  {
    src: "/demo-dashboard.png",
    label: "Live Active Analytics Dashboard",
    desc: "Real-time 8-emotion timeline, radar chart, and vocal biomarker tracking — all updating every 3 seconds.",
  },
  {
    src: "/demo-history.png",
    label: "Analysis History & Session Review",
    desc: "Replay any session with audio playback, risk index gauge, emotion distribution charts, and exportable reports.",
  },
];

const DemoModal = ({ onClose, onTryNow }: { onClose: () => void; onTryNow: () => void }) => {
  const [slide, setSlide] = useState(0);

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/85 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl rounded-3xl overflow-hidden border border-white/10 shadow-2xl bg-[#0B0F19] flex flex-col"
        style={{ maxHeight: "90vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="text-[10px] font-bold text-primary uppercase tracking-widest">Product Demo</span>
            </div>
            <h3 className="text-lg font-bold text-white">PsychVoice AI — Clinical Walkthrough</h3>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-slate-400 hover:text-white transition-all border border-white/5"
          >
            <X size={18} />
          </button>
        </div>

        {/* Slide Image */}
        <div className="relative bg-black flex-1 overflow-hidden" style={{ minHeight: "400px" }}>
          <img
            key={slide}
            src={DEMO_SLIDES[slide].src}
            alt={DEMO_SLIDES[slide].label}
            className="w-full h-full object-contain"
            style={{ animation: "fadeIn 0.3s ease" }}
          />
          {/* Gradient vignette */}
          <div className="absolute inset-0 pointer-events-none bg-gradient-to-t from-[#0B0F19]/80 via-transparent to-transparent" />

          {/* Slide Nav Arrows */}
          {slide > 0 && (
            <button
              onClick={() => setSlide(s => s - 1)}
              className="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/60 hover:bg-black/80 flex items-center justify-center text-white border border-white/10 transition-all"
            >
              <ChevronLeft size={20} />
            </button>
          )}
          {slide < DEMO_SLIDES.length - 1 && (
            <button
              onClick={() => setSlide(s => s + 1)}
              className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/60 hover:bg-black/80 flex items-center justify-center text-white border border-white/10 transition-all"
            >
              <ChevronRight size={20} />
            </button>
          )}

          {/* Slide Description Overlay */}
          <div className="absolute bottom-0 left-0 right-0 p-5">
            <div className="text-sm font-bold text-white mb-1">{DEMO_SLIDES[slide].label}</div>
            <div className="text-xs text-slate-400 max-w-lg">{DEMO_SLIDES[slide].desc}</div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 flex items-center justify-between border-t border-white/5 bg-white/[0.02] shrink-0">
          {/* Dot Navigation */}
          <div className="flex items-center gap-2">
            {DEMO_SLIDES.map((_, i) => (
              <button
                key={i}
                onClick={() => setSlide(i)}
                className={`rounded-full transition-all ${i === slide ? "w-6 h-2 bg-primary" : "w-2 h-2 bg-white/20 hover:bg-white/40"}`}
              />
            ))}
            <span className="text-xs text-slate-500 ml-2">{slide + 1} / {DEMO_SLIDES.length}</span>
          </div>
          <button
            onClick={onTryNow}
            className="bg-primary hover:bg-blue-600 text-white px-6 py-2.5 rounded-xl text-sm font-bold transition-all flex items-center gap-2 shadow-lg shadow-primary/20"
          >
            Launch Clinical Portal <ArrowRight size={14} />
          </button>
        </div>
      </div>
      <style>{`@keyframes fadeIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }`}</style>
    </div>
  );
};


export const Home = () => {
  const navigate = useNavigate();
  const [showDemo, setShowDemo] = useState(false);

  return (
    <div className="min-h-screen bg-[#0B0F19] text-white selection:bg-primary/30">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 bg-[#0B0F19]/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-accent to-primary flex items-center justify-center shadow-lg shadow-primary/20">
              <Activity size={20} className="text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight">PsychVoice <span className="text-primary">AI</span></span>
          </div>
          
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#importance" className="hover:text-white transition-colors">Clinical Importance</a>
            <a href="#security" className="hover:text-white transition-colors">Security</a>
          </div>

          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate("/auth")}
              className="text-sm font-medium text-slate-300 hover:text-white transition-colors px-4 py-2"
            >
              Sign In
            </button>
            <button 
              onClick={() => navigate("/auth")}
              className="bg-primary hover:bg-blue-600 px-6 py-2.5 rounded-xl text-sm font-bold transition-all shadow-lg shadow-primary/20 hover:shadow-primary/40 transform hover:-translate-y-0.5"
            >
              Get Started
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-40 pb-20 px-6 relative overflow-hidden">
        {/* Animated Orbs */}
        <div className="absolute top-40 left-[-10%] w-[40%] h-[40%] bg-primary/20 blur-[120px] rounded-full animate-pulse" />
        <div className="absolute bottom-20 right-[-5%] w-[30%] h-[30%] bg-accent/15 blur-[100px] rounded-full animate-pulse" style={{ animationDelay: '2s' }} />

        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-16 items-center relative z-10">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-bold text-primary tracking-widest uppercase">
              <Sparkles size={14} />
              The Future of Psychiatric Diagnostics
            </div>
            
            <h1 className="text-6xl lg:text-7xl font-bold leading-[1.1] tracking-tight">
              Unlock the <span className="bg-clip-text text-transparent bg-gradient-to-r from-white via-white to-slate-500">Silent Language</span> of the Mind.
            </h1>
            
            <p className="text-xl text-slate-400 leading-relaxed max-w-xl">
              PsychVoice AI identifies objective vocal biomarkers to assist clinicians in the early detection of depression, anxiety, and mood disorders through real-time emotional intelligence.
            </p>

            <div className="flex flex-wrap gap-4 pt-4">
              <button 
                onClick={() => navigate("/auth")}
                className="bg-primary hover:bg-blue-600 px-8 py-4 rounded-2xl text-lg font-bold transition-all flex items-center gap-3 shadow-2xl shadow-primary/30 group"
              >
                Launch Professional Portal
                <ArrowRight className="group-hover:translate-x-1 transition-transform" />
              </button>
              <button
                onClick={() => setShowDemo(true)}
                className="bg-white/5 hover:bg-white/10 border border-white/10 px-8 py-4 rounded-2xl text-lg font-bold transition-all flex items-center gap-3 group hover:border-primary/30"
              >
                Watch Demo
                <Play size={18} fill="currentColor" className="group-hover:text-primary transition-colors" />
              </button>
            </div>

            <div className="flex items-center gap-8 pt-8 border-t border-white/5">
              <div>
                <div className="text-2xl font-bold">98.4%</div>
                <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Classification Accuracy</div>
              </div>
              <div className="w-px h-10 bg-white/10" />
              <div>
                <div className="text-2xl font-bold">Real-time</div>
                <div className="text-xs text-slate-500 uppercase tracking-widest font-bold">Latency Analysis</div>
              </div>
            </div>
          </div>

          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary to-accent rounded-[2rem] blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
            <div className="relative rounded-[2rem] overflow-hidden border border-white/10 shadow-2xl">
              <img 
                src="/assets/hero.png" 
                alt="PsychVoice AI Interface" 
                className="w-full h-auto object-cover transform transition duration-700 hover:scale-105"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Importance Section */}
      <section id="importance" className="py-24 px-6 bg-white/[0.02] border-y border-white/5">
        <div className="max-w-7xl mx-auto">
          <div className="text-center space-y-4 mb-16">
            <h2 className="text-4xl font-bold">The Clinical Imperative</h2>
            <p className="text-lg text-slate-400 max-w-2xl mx-auto">
              Why objective emotional detection is the new gold standard in psychiatric care.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-surface/30 p-8 rounded-3xl border border-white/5 hover:border-primary/20 transition-all group">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-6 group-hover:scale-110 transition-transform">
                <HeartPulse size={28} />
              </div>
              <h3 className="text-xl font-bold mb-4">Precision Intervention</h3>
              <p className="text-slate-400 leading-relaxed italic text-sm">
                Emotion detection allows for the identification of subtle vocal tremors and prosody shifts that are imperceptible to the human ear but clinically significant for diagnosing early-stage mania or depression.
              </p>
            </div>

            <div className="bg-surface/30 p-8 rounded-3xl border border-white/5 hover:border-accent/20 transition-all group">
              <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center text-accent mb-6 group-hover:scale-110 transition-transform">
                <Brain size={28} />
              </div>
              <h3 className="text-xl font-bold mb-4">Bias-Free Diagnostics</h3>
              <p className="text-slate-400 leading-relaxed italic text-sm">
                By removing clinician subjectivity and patient self-reporting bias, PsychVoice provides a purely physiological data stream of emotional state, making your diagnostics more "legal" and evidence-based.
              </p>
            </div>

            <div className="bg-surface/30 p-8 rounded-3xl border border-white/5 hover:border-primary/20 transition-all group">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-6 group-hover:scale-110 transition-transform">
                <BarChart3 size={28} />
              </div>
              <h3 className="text-xl font-bold mb-4">Longitudinal Tracking</h3>
              <p className="text-slate-400 leading-relaxed italic text-sm">
                Visualize treatment efficacy through quantitative emotional graphs. Prove medication response or therapeutic progress with objective biomarker reports accumulated over multiple sessions.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-7xl mx-auto grid md:grid-cols-2 gap-20 items-center">
          <div className="order-2 md:order-1 grid grid-cols-2 gap-4">
            <div className="space-y-4">
              <div className="bg-surface/30 p-6 rounded-2xl border border-white/5 aspect-square flex flex-col justify-center items-center text-center gap-4">
                <Ear size={32} className="text-primary" />
                <span className="text-xs font-bold uppercase tracking-widest text-slate-500">Live Prosody Detection</span>
              </div>
              <div className="bg-primary/10 p-6 rounded-2xl border border-primary/20 aspect-square flex flex-col justify-center items-center text-center gap-4">
                <Brain size={32} className="text-primary" />
                <span className="text-xs font-bold uppercase tracking-widest text-primary">8-Class Emotion AI</span>
              </div>
            </div>
            <div className="space-y-4 pt-8">
              <div className="bg-accent/10 p-6 rounded-2xl border border-accent/20 aspect-square flex flex-col justify-center items-center text-center gap-4">
                <Activity size={32} className="text-accent" />
                <span className="text-xs font-bold uppercase tracking-widest text-accent">Biomarker Syncing</span>
              </div>
              <div className="bg-surface/30 p-6 rounded-2xl border border-white/5 aspect-square flex flex-col justify-center items-center text-center gap-4">
                <ShieldCheck size={32} className="text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-widest text-slate-500">HIPAA Secure Vault</span>
              </div>
            </div>
          </div>

          <div className="order-1 md:order-2 space-y-8">
            <h2 className="text-4xl font-bold tracking-tight">Enterprise-Grade <span className="text-primary">Voice Intelligence</span>.</h2>
            <p className="text-lg text-slate-400 leading-relaxed">
              Our proprietary XLSR-Wav2Vec2 engine analyzes over 150 vocal features per second, including jitter, shimmer, and fundamental frequency variability, to provide clinical-grade emotional insights.
            </p>
            <ul className="space-y-4 text-slate-300">
              <li className="flex items-start gap-4 italic text-sm">
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center mt-1">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                </div>
                Real-time diarization to isolate patient vs. clinician voices.
              </li>
              <li className="flex items-start gap-4 italic text-sm">
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center mt-1">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                </div>
                Automated Depression Severity Indexing based on vocal energy.
              </li>
              <li className="flex items-start gap-4 italic text-sm">
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center mt-1">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                </div>
                End-to-end encrypted session storage for total data sovereignty.
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-white/5 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-3 opacity-50">
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
              <Activity size={16} />
            </div>
            <span className="text-sm font-bold">PsychVoice AI</span>
          </div>
          <div className="text-xs text-slate-500">
            © 2026 Advanced Neuro Diagnostics. All rights reserved. HIPAA Compliant. 
          </div>
        </div>
      </footer>

      {/* ── Demo Modal ──────────────────────────────────────────────── */}
      {showDemo && <DemoModal onClose={() => setShowDemo(false)} onTryNow={() => { setShowDemo(false); navigate("/auth"); }} />}
    </div>
  );
};
