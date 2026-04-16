import { BrowserRouter, Routes, Route } from "react-router-dom";
import { motion } from "framer-motion";
import { Layout } from "./components/layout/Layout";
import { ProtectedRoute } from "./components/common/ProtectedRoute";
import { Auth } from "./pages/Auth";
import { Patients } from "./pages/Patients";
import { Sessions } from "./pages/Sessions";

import { Home } from "./pages/Home";
import { Dashboard } from "./pages/Dashboard";

const AmbientBackground = () => (
  <div className="fixed inset-0 overflow-hidden pointer-events-none z-[-10]">
    <motion.div
      animate={{ x: [0, 50, 0], y: [0, -30, 0], scale: [1, 1.1, 1] }}
      transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
      className="absolute -top-[20%] -right-[10%] w-[50%] h-[50%] rounded-full bg-primary/20 blur-[120px]"
    />
    <motion.div
      animate={{ x: [0, -40, 0], y: [0, 40, 0], scale: [1, 1.2, 1] }}
      transition={{ duration: 18, repeat: Infinity, ease: "easeInOut", delay: 2 }}
      className="absolute -bottom-[20%] -left-[10%] w-[60%] h-[60%] rounded-full bg-accent/15 blur-[140px]"
    />
  </div>
);

function App() {
  return (
    <BrowserRouter>
      <AmbientBackground />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/auth" element={<Auth />} />
        
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/patients" element={<Patients />} />
            <Route path="/sessions" element={<Sessions />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
