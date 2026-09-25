import { useState } from "react";
import { Loader2, KeyRound } from "lucide-react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function ForcePasswordChange() {
  const { refreshUser } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (next !== confirm) {
      setError("New passwords don't match");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.post("/api/auth/change-password", { current_password: current, new_password: next });
      refreshUser({ must_change_password: false });
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink-900/60 p-4">
      <form onSubmit={submit} className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <div className="flex items-center gap-2 mb-1">
          <KeyRound size={18} className="text-atlas-600" />
          <h2 className="font-bold text-ink-900">Set a new password</h2>
        </div>
        <p className="text-sm text-slate-500 mb-4">For security, you must change your temporary password before continuing.</p>
        {error && <div className="mb-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}
        <div className="space-y-3">
          <div>
            <label className="label">Current (temporary) password</label>
            <input className="input" type="password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div>
            <label className="label">New password</label>
            <input className="input" type="password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
          </div>
          <div>
            <label className="label">Confirm new password</label>
            <input className="input" type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
        </div>
        <button className="btn-primary w-full mt-5" disabled={busy}>
          {busy && <Loader2 size={15} className="animate-spin" />}
          Update password
        </button>
      </form>
    </div>
  );
}
