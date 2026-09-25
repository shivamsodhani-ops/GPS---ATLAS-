import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  MessageCircleQuestion,
  FolderOpen,
  Users,
  ShieldCheck,
  BarChart3,
  LogOut,
  Leaf,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/ask", label: "Ask ATLAS", icon: MessageCircleQuestion },
  { to: "/library", label: "Document Library", icon: FolderOpen },
];

const ADMIN_NAV = [
  { to: "/admin/users", label: "Users & Departments", icon: Users },
  { to: "/admin/audit", label: "Audit Log", icon: ShieldCheck },
  { to: "/admin/analytics", label: "Analytics", icon: BarChart3 },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const canSeeAnalytics = user?.role === "admin" || user?.role === "manager";
  const isAdmin = user?.role === "admin";

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-64 shrink-0 bg-ink-900 text-slate-200 flex flex-col">
        <div className="px-5 py-5 flex items-center gap-2 border-b border-white/10">
          <div className="h-8 w-8 rounded-lg bg-atlas-500 flex items-center justify-center">
            <Leaf size={18} className="text-white" />
          </div>
          <div>
            <div className="font-bold text-white leading-tight">GPS ATLAS</div>
            <div className="text-[11px] text-slate-400 leading-tight">Information Intelligence</div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive ? "bg-atlas-700 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <item.icon size={17} />
              {item.label}
            </NavLink>
          ))}

          {(canSeeAnalytics || isAdmin) && (
            <>
              <div className="pt-4 pb-1 px-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Admin
              </div>
              {ADMIN_NAV.filter((item) => isAdmin || item.to === "/admin/analytics").map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                      isActive ? "bg-atlas-700 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"
                    }`
                  }
                >
                  <item.icon size={17} />
                  {item.label}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-2 px-2 py-2">
            <div className="h-8 w-8 rounded-full bg-atlas-600 flex items-center justify-center text-xs font-bold text-white">
              {(user?.name || "?").split(" ").map((p) => p[0]).slice(0, 2).join("")}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-white truncate">{user?.name}</div>
              <div className="text-[11px] text-slate-400 truncate">
                {user?.department_name || "No department"} · {user?.role}
              </div>
            </div>
          </div>
          <button onClick={handleLogout} className="mt-1 w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 bg-slate-50">
        <div className="max-w-6xl mx-auto px-6 py-8">{children}</div>
      </main>
    </div>
  );
}
