import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";
import { Loading } from "../ui/Feedback";

export function ProtectedRoute() { const { user, loading } = useAuth(); const location = useLocation(); if (loading) return <Loading label="Restoring your secure session" />; return user ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} />; }
export function AdminRoute() { const { user } = useAuth(); return user?.role === "admin" ? <Outlet /> : <Navigate to="/dashboard" replace />; }
