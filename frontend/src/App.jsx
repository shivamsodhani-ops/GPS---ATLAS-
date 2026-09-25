import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "./context/AuthContext";
import Layout from "./components/Layout";
import ForcePasswordChange from "./components/ForcePasswordChange";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Ask from "./pages/Ask";
import Library from "./pages/Library";
import AdminUsers from "./pages/admin/Users";
import AuditLog from "./pages/admin/AuditLog";
import Analytics from "./pages/admin/Analytics";

function ProtectedRoute({ children, adminOnly, managerPlus }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-atlas-600" size={28} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  if (managerPlus && !["admin", "manager"].includes(user.role)) return <Navigate to="/" replace />;

  return (
    <Layout>
      {user.must_change_password && <ForcePasswordChange />}
      {children}
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ask"
        element={
          <ProtectedRoute>
            <Ask />
          </ProtectedRoute>
        }
      />
      <Route
        path="/library"
        element={
          <ProtectedRoute>
            <Library />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <ProtectedRoute adminOnly>
            <AdminUsers />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <ProtectedRoute adminOnly>
            <AuditLog />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/analytics"
        element={
          <ProtectedRoute managerPlus>
            <Analytics />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
