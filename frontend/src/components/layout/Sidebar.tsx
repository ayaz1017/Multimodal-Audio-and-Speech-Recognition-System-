import { NavLink, useNavigate } from "react-router-dom";
import { Activity, Users, FileText, LogOut } from "lucide-react";
import { useStore } from "../../store/useStore";

export const Sidebar = () => {
  const logout = useStore((state) => state.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <aside className="w-64 h-screen bg-surface border-r border-white/5 flex flex-col pt-8 pb-4">
      <div className="px-6 mb-10 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-accent to-primary flex items-center justify-center">
          <Activity size={18} className="text-white" />
        </div>
        <h1 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          PsychVoice AI
        </h1>
      </div>

      <nav className="flex-1 px-4 space-y-2">
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              isActive
                ? "bg-primary/10 text-primary font-medium"
                : "text-slate-400 hover:text-white hover:bg-white/5"
            }`
          }
        >
          <Activity size={18} />
          Active Session
        </NavLink>
        <NavLink
          to="/patients"
          className={({ isActive }) =>
            `flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              isActive
                ? "bg-primary/10 text-primary font-medium"
                : "text-slate-400 hover:text-white hover:bg-white/5"
            }`
          }
        >
          <Users size={18} />
          Patients
        </NavLink>
        <NavLink
          to="/sessions"
          className={({ isActive }) =>
            `flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              isActive
                ? "bg-primary/10 text-primary font-medium"
                : "text-slate-400 hover:text-white hover:bg-white/5"
            }`
          }
        >
          <FileText size={18} />
          Analysis History
        </NavLink>
      </nav>

      <div className="px-4">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-400/10 transition-all"
        >
          <LogOut size={18} />
          Disconnect
        </button>
      </div>
    </aside>
  );
};
