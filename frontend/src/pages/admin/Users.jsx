import { useEffect, useState } from "react";
import { Plus, ShieldOff, ShieldCheck, Loader2, Building2 } from "lucide-react";
import { api, apiErrorMessage } from "../../api/client";
import Modal from "../../components/Modal";
import { ROLES } from "../../constants";
import { formatDate } from "../../utils/format";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [showUserModal, setShowUserModal] = useState(false);
  const [showDeptModal, setShowDeptModal] = useState(false);
  const [error, setError] = useState("");

  function load() {
    api.get("/api/users").then((res) => setUsers(res.data));
    api.get("/api/departments").then((res) => setDepartments(res.data));
  }

  useEffect(load, []);

  async function toggleActive(user) {
    try {
      await api.patch(`/api/users/${user.id}`, { is_active: !user.is_active });
      load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  const deptNameById = Object.fromEntries(departments.map((d) => [d.id, d.name]));

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Users &amp; Departments</h1>
          <p className="text-slate-500 mt-1 text-sm">Manage who has an ATLAS account and which department they belong to.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowDeptModal(true)} className="btn-secondary">
            <Building2 size={15} /> New department
          </button>
          <button onClick={() => setShowUserModal(true)} className="btn-primary">
            <Plus size={15} /> New user
          </button>
        </div>
      </div>

      {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}

      <div className="card divide-y divide-slate-100">
        {users.map((u) => (
          <div key={u.id} className="flex items-center gap-3 px-4 py-3">
            <div className="h-9 w-9 rounded-full bg-atlas-100 text-atlas-700 flex items-center justify-center font-bold text-xs shrink-0">
              {u.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-ink-900 truncate flex items-center gap-2">
                {u.name}
                {!u.is_active && <span className="badge bg-slate-200 text-slate-600">deactivated</span>}
                {u.must_change_password && <span className="badge bg-amber-100 text-amber-700">password reset pending</span>}
              </div>
              <div className="text-xs text-slate-500 truncate">
                {u.email} · {u.department_name || "No department"} · joined {formatDate(u.created_at)}
              </div>
            </div>
            <span className={`badge ${u.role === "admin" ? "bg-purple-100 text-purple-700" : u.role === "manager" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"}`}>
              {u.role}
            </span>
            <button onClick={() => toggleActive(u)} className="text-slate-400 hover:text-ink-700 ml-2" title={u.is_active ? "Deactivate" : "Reactivate"}>
              {u.is_active ? <ShieldOff size={16} /> : <ShieldCheck size={16} className="text-emerald-600" />}
            </button>
          </div>
        ))}
        {users.length === 0 && <div className="p-8 text-center text-slate-400 text-sm">No users yet.</div>}
      </div>

      <div className="card p-5">
        <h2 className="font-semibold text-ink-900 mb-3 flex items-center gap-2">
          <Building2 size={16} /> Departments
        </h2>
        <div className="flex flex-wrap gap-2">
          {departments.map((d) => (
            <span key={d.id} className="badge bg-slate-100 text-slate-700 border border-slate-200">
              {d.name} <span className="text-slate-400">({d.code})</span>
            </span>
          ))}
        </div>
      </div>

      {showUserModal && (
        <NewUserModal
          departments={departments}
          onClose={() => setShowUserModal(false)}
          onCreated={() => {
            setShowUserModal(false);
            load();
          }}
        />
      )}
      {showDeptModal && (
        <NewDeptModal
          onClose={() => setShowDeptModal(false)}
          onCreated={() => {
            setShowDeptModal(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function NewUserModal({ departments, onClose, onCreated }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("employee");
  const [departmentId, setDepartmentId] = useState(departments[0]?.id || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/users", { name, email, password, role, department_id: departmentId || null });
      onCreated();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Create a new user" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}
        <div>
          <label className="label">Full name</label>
          <input className="input" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label">Temporary password</label>
          <input className="input" type="text" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="text-xs text-slate-400 mt-1">They'll be asked to change it on first login.</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Role</label>
            <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Department</label>
            <select className="input" value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button className="btn-primary w-full" disabled={busy}>
          {busy && <Loader2 size={15} className="animate-spin" />}
          Create user
        </button>
      </form>
    </Modal>
  );
}

function NewDeptModal({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/departments", { name, code });
      onCreated();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Create a new department" onClose={onClose} width="max-w-sm">
      <form onSubmit={submit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}
        <div>
          <label className="label">Name</label>
          <input className="input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Human Resources" />
        </div>
        <div>
          <label className="label">Short code</label>
          <input className="input" required value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="e.g. HR" maxLength={10} />
        </div>
        <button className="btn-primary w-full" disabled={busy}>
          {busy && <Loader2 size={15} className="animate-spin" />}
          Create department
        </button>
      </form>
    </Modal>
  );
}
