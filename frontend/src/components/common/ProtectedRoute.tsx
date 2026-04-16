import { Navigate, Outlet } from "react-router-dom";
import { useStore } from "../../store/useStore";

export const ProtectedRoute = () => {
  const token = useStore((state) => state.token);

  if (!token) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};
