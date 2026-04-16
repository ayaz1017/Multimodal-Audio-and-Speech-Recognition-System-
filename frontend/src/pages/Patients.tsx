import { useState, useEffect } from "react";
import { Users, Plus, Loader2, Mic } from "lucide-react";
import { api } from "../services/api";
import { useNavigate } from "react-router-dom";
export const Patients = () => {
  const [patients, setPatients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editPatient, setEditPatient] = useState<any>(null);
  const [form, setForm] = useState({ full_name: "", patient_code: "" });
  const navigate = useNavigate();

  const fetchPatients = async () => {
    try {
      const res = await api.get("/patients");
      setPatients(res.data.patients);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPatients();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editPatient) {
        await api.put(`/patients/${editPatient.id}`, form);
      } else {
        await api.post("/patients", form);
      }
      setShowModal(false);
      setEditPatient(null);
      setForm({ full_name: "", patient_code: "" });
      fetchPatients();
    } catch (err) {
      console.error(err);
    }
  };

  const openEdit = (patient: any) => {
    setEditPatient(patient);
    setForm({ full_name: patient.full_name, patient_code: patient.patient_code });
    setShowModal(true);
  };

  const handleStartSession = (patientId: string) => {
    navigate("/dashboard", { state: { selectedPatientId: patientId } });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Patients</h1>
          <p className="text-slate-400 mt-1">Manage your active case files.</p>
        </div>
        <button 
          onClick={() => setShowModal(true)}
          className="bg-primary/20 text-primary border border-primary/50 hover:bg-primary/30 px-6 py-2.5 rounded-xl font-medium transition-all flex items-center gap-2"
        >
          <Plus size={18} />
          Register Patient
        </button>
      </div>
      
      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="animate-spin text-primary" size={32} />
        </div>
      ) : patients.length === 0 ? (
        <div className="flex-1 border border-white/5 bg-surface/50 rounded-2xl p-8 flex flex-col items-center justify-center">
          <Users size={48} className="text-slate-600 mb-4" />
          <h3 className="text-xl font-medium text-slate-300">No Patients Registered</h3>
          <p className="text-slate-500 mt-2 text-center max-w-sm">
            You haven't added any patients to your roster yet. Click the button above to register your first patient.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {patients.map((p) => (
            <div key={p.id} className="bg-surface/50 border border-white/5 p-6 rounded-2xl hover:border-primary/30 transition-all group">
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold">
                  {p.full_name.charAt(0)}
                </div>
                <span className="text-[10px] font-mono text-slate-500 bg-white/5 px-2 py-1 rounded">
                  {p.patient_code}
                </span>
              </div>
              <h4 className="text-lg font-bold text-white group-hover:text-primary transition-colors">{p.full_name}</h4>
              <p className="text-sm text-slate-400 mt-1">ID: {p.id.substring(0, 8)}...</p>
              <div className="mt-4 pt-4 border-t border-white/5 flex gap-2">
                <button 
                  onClick={() => handleStartSession(p.id)}
                  className="flex-1 bg-primary/10 hover:bg-primary/20 text-primary text-xs py-2 rounded-lg transition-colors flex items-center justify-center gap-1"
                >
                  <Mic size={14} /> Start
                </button>
                <button 
                  onClick={() => openEdit(p)}
                  className="flex-1 bg-white/5 hover:bg-white/10 text-xs py-2 rounded-lg transition-colors"
                >
                  Edit
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal Integration */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-surface border border-white/10 p-8 rounded-2xl w-full max-w-md shadow-2xl">
            <h2 className="text-2xl font-bold text-white mb-6">
              {editPatient ? "Edit Patient Record" : "Register New Patient"}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Full Name</label>
                <input
                  autoFocus
                  className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary"
                  placeholder="e.g. John Doe"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Patient Code</label>
                <input
                  className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-primary"
                  placeholder="e.g. P1002"
                  value={form.patient_code}
                  onChange={(e) => setForm({ ...form, patient_code: e.target.value })}
                  required
                />
              </div>
              <div className="flex gap-4 mt-8">
                <button 
                  type="button"
                  onClick={() => { setShowModal(false); setEditPatient(null); setForm({ full_name: "", patient_code: "" }); }}
                  className="flex-1 bg-white/5 hover:bg-white/10 text-white py-3 rounded-xl font-medium transition-all"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  className="flex-1 bg-primary hover:bg-blue-600 text-white py-3 rounded-xl font-medium shadow-lg shadow-primary/20 transition-all"
                >
                  {editPatient ? "Update Record" : "Create Record"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
