import React, { useState } from "react";
import { useStore } from "../store/useStore";
import { Activity } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";

export const Auth = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("doctor1@example.com");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("pass123");
  const [error, setError] = useState("");
  const setToken = useStore((state: any) => state.setToken);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      if (isLogin) {
        // Login: Expects { email, password }
        const res = await api.post("/auth/login", { email, password });
        // Response is { user, tokens: { access_token, ... } }
        setToken(res.data.tokens.access_token);
        navigate("/dashboard");
      } else {
        // Register: Expects { email, password, full_name, role }
        if (!fullName) {
          setError("Full name is required for registration");
          return;
        }
        await api.post("/auth/register", { 
          email, 
          password, 
          full_name: fullName, 
          role: "doctor" 
        });
        setIsLogin(true);
        setError("Account created! Please log in.");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Authentication failed");
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center relative overflow-hidden">
      {/* Background Orbs */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-primary/20 blur-[150px] rounded-full pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-accent/20 blur-[150px] rounded-full pointer-events-none" />

      <div className="z-10 w-full max-w-md p-8 bg-surface/50 backdrop-blur-xl border border-white/5 rounded-2xl shadow-2xl">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-accent to-primary flex items-center justify-center mb-4">
            <Activity size={24} className="text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white">PsychVoice AI</h2>
          <p className="text-slate-400 text-sm mt-2">
            {isLogin ? "Welcome back, Doctor" : "Create your portal account"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Full Name</label>
              <input
                type="text"
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
                placeholder="Dr. John Doe"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Email Address</label>
            <input
              type="email"
              className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
              placeholder="doctor@hospital.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
            <input
              type="password"
              className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <p className="text-red-400 text-sm mt-2 text-center">{error}</p>}

          <button
            type="submit"
            className="w-full mt-6 bg-primary hover:bg-blue-600 text-white font-medium py-3 rounded-xl transition-all shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)] transform hover:-translate-y-0.5"
          >
            {isLogin ? "Sign In" : "Sign Up"}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-slate-400 hover:text-white text-sm transition-colors"
          >
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
};
