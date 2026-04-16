import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { useStore } from "../../store/useStore";

export const Layout = () => {
  const sessionActive = useStore((state) => state.sessionActive);

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <header className="h-16 border-b border-white/5 flex items-center justify-between px-8 bg-surface/50 backdrop-blur-md">
          <h2 className="text-sm font-medium text-slate-300">Workspace</h2>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                {sessionActive ? (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                  </>
                ) : (
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-slate-500"></span>
                )}
              </span>
              <span className="text-xs font-semibold text-slate-400">
                {sessionActive ? "RECORDING LIVE" : "IDLE"}
              </span>
            </div>
            <div className="w-8 h-8 rounded-full bg-surface border border-white/10 ml-4"></div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-8 relative">
          {/* Glassmorphism Background Gradients */}
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 blur-[120px] rounded-full pointer-events-none" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-accent/10 blur-[120px] rounded-full pointer-events-none" />
          
          <div className="relative z-10 h-full">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
};
