import { useEffect, useState } from "react";
import { X, Download, History, Archive, UserPlus, AlertTriangle, Loader2 } from "lucide-react";
import { api, apiErrorMessage } from "../api/client";
import { formatBytes, formatDateTime, formatDate } from "../utils/format";
import { useAuth } from "../context/AuthContext";

export default function DocumentDrawer({ documentId, onClose, onArchived, onUploadNewVersion }) {
  const { user } = useAuth();
  const [doc, setDoc] = useState(null);
  const [versions, setVersions] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [grantEmail, setGrantEmail] = useState("");
  const [grantMsg, setGrantMsg] = useState("");

  useEffect(() => {
    if (!documentId) return;
    Promise.all([api.get(`/api/documents/${documentId}`), api.get(`/api/documents/${documentId}/versions`)])
      .then(([d, v]) => {
        setDoc(d.data);
        setVersions(v.data);
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, [documentId]);

  // Upload processing (text extraction/OCR + indexing) now finishes after
  // the upload request returns, so a fresh version can sit at "pending" for
  // a few seconds. Poll quietly until nothing's pending anymore, so the
  // status pill below flips to ok/failed/empty on its own instead of the
  // user needing to close and reopen the drawer to see it.
  useEffect(() => {
    if (!documentId) return;
    if (!versions.some((v) => v.extraction_status === "pending")) return;
    const interval = setInterval(() => {
      api.get(`/api/documents/${documentId}/versions`).then((v) => setVersions(v.data));
    }, 3000);
    return () => clearInterval(interval);
  }, [documentId, versions]);

  if (!documentId) return null;

  async function handleDownload() {
    const res = await api.get(`/api/documents/${documentId}/download`, { responseType: "blob" });
    const disposition = res.headers["content-disposition"] || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const url = window.URL.createObjectURL(res.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = match ? match[1] : (doc?.title || "document");
    link.click();
    window.URL.revokeObjectURL(url);
  }

  async function handleArchive() {
    if (!confirm(`Archive "${doc.title}"? It will be hidden from the library but kept for audit history.`)) return;
    setBusy(true);
    try {
      await api.delete(`/api/documents/${documentId}`);
      onArchived?.(documentId);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleGrant(e) {
    e.preventDefault();
    setGrantMsg("");
    try {
      const lookup = await api.get("/api/users/lookup", { params: { email: grantEmail.trim() } });
      await api.post(`/api/documents/${documentId}/grants`, { user_id: lookup.data.id });
      setGrantMsg(`Access granted to ${lookup.data.name}.`);
      setGrantEmail("");
    } catch (err) {
      setGrantMsg(apiErrorMessage(err, "No user found with that email"));
    }
  }

  const canManage = user?.role === "admin" || user?.role === "manager" || doc?.uploader_id === user?.id;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="flex-1 bg-ink-900/30" onClick={onClose} />
      <div className="w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Document details</span>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X size={18} />
          </button>
        </div>

        {error && <div className="m-5 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}

        {!doc ? (
          <div className="p-8 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>
        ) : (
          <div className="p-5 space-y-5">
            <div>
              <h2 className="font-bold text-lg text-ink-900">{doc.title}</h2>
              <div className="flex flex-wrap gap-1.5 mt-2">
                <span className="badge bg-slate-100 text-slate-600">{doc.doc_type}</span>
                <span className="badge bg-atlas-50 text-atlas-700">{doc.department_name}</span>
                {doc.tags.map((t) => (
                  <span key={t} className="badge bg-slate-50 text-slate-500 border border-slate-200">
                    #{t}
                  </span>
                ))}
              </div>
              {doc.description && <p className="text-sm text-slate-600 mt-3">{doc.description}</p>}
            </div>

            {doc.expiry_date && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 flex items-center gap-2">
                <AlertTriangle size={14} />
                Expires {formatDate(doc.expiry_date)} ({doc.expiry_source === "detected" ? "auto-detected, verify" : "manually set"})
              </div>
            )}

            <div className="grid grid-cols-2 gap-2">
              <button onClick={handleDownload} className="btn-secondary">
                <Download size={15} /> Download
              </button>
              {canManage && (
                <button onClick={() => onUploadNewVersion(doc)} className="btn-secondary">
                  <History size={15} /> New version
                </button>
              )}
            </div>

            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Version history</h3>
              <div className="space-y-2">
                {versions.map((v) => (
                  <div key={v.id} className="flex items-center justify-between text-sm rounded-lg border border-slate-200 px-3 py-2">
                    <div>
                      <div className="font-medium text-ink-900">
                        v{v.version_number} · {v.original_filename}
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatBytes(v.file_size_bytes)} · {formatDateTime(v.uploaded_at)}
                      </div>
                    </div>
                    <StatusPill status={v.extraction_status} />
                  </div>
                ))}
              </div>
            </div>

            {canManage && (
              <div>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Grant access to a specific person</h3>
                <form onSubmit={handleGrant} className="flex gap-2">
                  <input
                    className="input"
                    type="email"
                    placeholder="colleague@gpsrenewables.com"
                    value={grantEmail}
                    onChange={(e) => setGrantEmail(e.target.value)}
                  />
                  <button className="btn-secondary shrink-0">
                    <UserPlus size={15} />
                  </button>
                </form>
                {grantMsg && <p className="text-xs text-slate-500 mt-1.5">{grantMsg}</p>}
              </div>
            )}

            {canManage && (
              <button onClick={handleArchive} disabled={busy} className="btn-danger w-full">
                {busy ? <Loader2 size={15} className="animate-spin" /> : <Archive size={15} />} Archive document
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    ok: "bg-emerald-100 text-emerald-700",
    pending: "bg-slate-100 text-slate-500",
    failed: "bg-red-100 text-red-700",
    empty: "bg-amber-100 text-amber-700",
  };
  return <span className={`badge ${map[status] || map.pending}`}>{status}</span>;
}
import { useEffect, useState } from "react";
import { X, Download, History, Archive, UserPlus, AlertTriangle, Loader2 } from "lucide-react";
import { api, apiErrorMessage } from "../api/client";
import { formatBytes, formatDateTime, formatDate } from "../utils/format";
import { useAuth } from "../context/AuthContext";

export default function DocumentDrawer({ documentId, onClose, onArchived, onUploadNewVersion }) {
  const { user } = useAuth();
  const [doc, setDoc] = useState(null);
  const [versions, setVersions] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [grantEmail, setGrantEmail] = useState("");
  const [grantMsg, setGrantMsg] = useState("");

  useEffect(() => {
    if (!documentId) return;
    Promise.all([api.get(`/api/documents/${documentId}`), api.get(`/api/documents/${documentId}/versions`)])
      .then(([d, v]) => {
        setDoc(d.data);
        setVersions(v.data);
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, [documentId]);

  if (!documentId) return null;

  async function handleDownload() {
    const res = await api.get(`/api/documents/${documentId}/download`, { responseType: "blob" });
    const disposition = res.headers["content-disposition"] || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const url = window.URL.createObjectURL(res.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = match ? match[1] : (doc?.title || "document");
    link.click();
    window.URL.revokeObjectURL(url);
  }

  async function handleArchive() {
    if (!confirm(`Archive "${doc.title}"? It will be hidden from the library but kept for audit history.`)) return;
    setBusy(true);
    try {
      await api.delete(`/api/documents/${documentId}`);
      onArchived?.(documentId);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleGrant(e) {
    e.preventDefault();
    setGrantMsg("");
    try {
      const lookup = await api.get("/api/users/lookup", { params: { email: grantEmail.trim() } });
      await api.post(`/api/documents/${documentId}/grants`, { user_id: lookup.data.id });
      setGrantMsg(`Access granted to ${lookup.data.name}.`);
      setGrantEmail("");
    } catch (err) {
      setGrantMsg(apiErrorMessage(err, "No user found with that email"));
    }
  }

  const canManage = user?.role === "admin" || user?.role === "manager" || doc?.uploader_id === user?.id;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="flex-1 bg-ink-900/30" onClick={onClose} />
      <div className="w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Document details</span>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X size={18} />
          </button>
        </div>

        {error && <div className="m-5 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}

        {!doc ? (
          <div className="p-8 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>
        ) : (
          <div className="p-5 space-y-5">
            <div>
              <h2 className="font-bold text-lg text-ink-900">{doc.title}</h2>
              <div className="flex flex-wrap gap-1.5 mt-2">
                <span className="badge bg-slate-100 text-slate-600">{doc.doc_type}</span>
                <span className="badge bg-atlas-50 text-atlas-700">{doc.department_name}</span>
                {doc.tags.map((t) => (
                  <span key={t} className="badge bg-slate-50 text-slate-500 border border-slate-200">
                    #{t}
                  </span>
                ))}
              </div>
              {doc.description && <p className="text-sm text-slate-600 mt-3">{doc.description}</p>}
            </div>

            {doc.expiry_date && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 flex items-center gap-2">
                <AlertTriangle size={14} />
                Expires {formatDate(doc.expiry_date)} ({doc.expiry_source === "detected" ? "auto-detected, verify" : "manually set"})
              </div>
            )}

            <div className="grid grid-cols-2 gap-2">
              <button onClick={handleDownload} className="btn-secondary">
                <Download size={15} /> Download
              </button>
              {canManage && (
                <button onClick={() => onUploadNewVersion(doc)} className="btn-secondary">
                  <History size={15} /> New version
                </button>
              )}
            </div>

            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Version history</h3>
              <div className="space-y-2">
                {versions.map((v) => (
                  <div key={v.id} className="flex items-center justify-between text-sm rounded-lg border border-slate-200 px-3 py-2">
                    <div>
                      <div className="font-medium text-ink-900">
                        v{v.version_number} · {v.original_filename}
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatBytes(v.file_size_bytes)} · {formatDateTime(v.uploaded_at)}
                      </div>
                    </div>
                    <StatusPill status={v.extraction_status} />
                  </div>
                ))}
              </div>
            </div>

            {canManage && (
              <div>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Grant access to a specific person</h3>
                <form onSubmit={handleGrant} className="flex gap-2">
                  <input
                    className="input"
                    type="email"
                    placeholder="colleague@gpsrenewables.com"
                    value={grantEmail}
                    onChange={(e) => setGrantEmail(e.target.value)}
                  />
                  <button className="btn-secondary shrink-0">
                    <UserPlus size={15} />
                  </button>
                </form>
                {grantMsg && <p className="text-xs text-slate-500 mt-1.5">{grantMsg}</p>}
              </div>
            )}

            {canManage && (
              <button onClick={handleArchive} disabled={busy} className="btn-danger w-full">
                {busy ? <Loader2 size={15} className="animate-spin" /> : <Archive size={15} />} Archive document
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    ok: "bg-emerald-100 text-emerald-700",
    pending: "bg-slate-100 text-slate-500",
    failed: "bg-red-100 text-red-700",
    empty: "bg-amber-100 text-amber-700",
  };
  return <span className={`badge ${map[status] || map.pending}`}>{status}</span>;
}
