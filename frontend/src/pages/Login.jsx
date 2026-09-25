import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Leaf, Lock, ShieldCheck, Search, Loader2, Info } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { apiErrorMessage } from "../api/client";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionResetNotice, setSessionResetNotice] = useState("");

  useEffect(() => {
    // Set by client.js when a request came back 401 outside of a login
    // attempt -- see the comment there. Read once and clear it so it
    // doesn't reappear on a manual logout or a later visit.
    try {
      if (sessionStorage.getItem("atlas_session_reset")) {
        setSessionResetNotice(
          "You were signed out because the server restarted -- on this app's current free hosting tier that also resets the database, so any password change or upload since the last restart didn't survive it either. This isn't something you did wrong."
        );
        sessionStorage.removeItem("atlas_session_reset");
      }
    } catch {
      /* ignore */
    }
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(apiErrorMessage(err, "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-ink-900 text-white p-12">
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-atlas-500 flex items-center justify-center">
            <Leaf size={20} />
          </div>
          <span className="text-lg font-bold">GPS ATLAS</span>
        </div>
        <div className="max-w-md">
          <h1 className="text-3xl font-bold leading-tight mb-4">
            Critical information, never lost. Instantly discoverable.
          </h1>
          <p className="text-slate-300 leading-relaxed">
            One secure depository for every contract, PO, drawing, MOM and report across GPS —
            with AI answers that cite the exact source document, filtered strictly by what you're
            authorized to see.
          </p>
          <div className="mt-8 space-y-3 text-sm text-slate-300">
            <div className="flex items-center gap-2"><ShieldCheck size={16} className="text-atlas-400" /> Viewer ID access control on every document and every answer</div>
            <div className="flex items-center gap-2"><Search size={16} className="text-atlas-400" /> Hybrid AI search with verifiable, clickable citations</div>
            <div className="flex items-center gap-2"><Lock size={16} className="text-atlas-400" /> Encrypted at rest, fully auditable</div>
          </div>
        </div>
        <div className="text-xs text-slate-500">GPS Renewables Private Limited · Built for GPS Ignite</div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={handleSubmit} className="w-full max-w-sm card p-8">
          <div className="lg:hidden flex items-center gap-2 mb-6">
            <div className="h-8 w-8 rounded-lg bg-atlas-600 flex items-center justify-center">
              <Leaf size={16} className="text-white" />
            </div>
            <span className="font-bold">GPS ATLAS</span>
          </div>
          <h2 className="text-xl font-bold text-ink-900">Sign in</h2>
          <p className="text-sm text-slate-500 mt-1 mb-6">Use your GPS ATLAS account to continue.</p>

          {sessionResetNotice && (
            <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 text-sm px-3 py-2 flex items-start gap-2">
              <Info size={15} className="shrink-0 mt-0.5" />
              <span>{sessionResetNotice}</span>
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                className="input"
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@gpsrenewables.com"
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                className="input"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
          </div>

          <button type="submit" disabled={busy} className="btn-primary w-full mt-6">
            {busy && <Loader2 size={16} className="animate-spin" />}
            Sign in
          </button>

          <p className="text-xs text-slate-400 mt-5 text-center">
            First time here? Ask your ATLAS administrator for an account.
          </p>
        </form>
      </div>
    </div>
  );
}
