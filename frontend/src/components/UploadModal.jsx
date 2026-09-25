import { useState } from "react";
import { UploadCloud, Loader2 } from "lucide-react";
import Modal from "./Modal";
import { api, apiErrorMessage } from "../api/client";
import { DOC_TYPES, ROLES } from "../constants";
import { useAuth } from "../context/AuthContext";

export default function UploadModal({ departments, onClose, onUploaded, supersedeDocument }) {
  const { user } = useAuth();
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState(supersedeDocument?.title || "");
  const [docType, setDocType] = useState(supersedeDocument?.doc_type || "contract");
  const [departmentId, setDepartmentId] = useState(supersedeDocument?.department_id || user?.department_id || departments[0]?.id || "");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [allowedDepts, setAllowedDepts] = useState([]);
  const [allowedRoles, setAllowedRoles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const canPickAnyDepartment = user?.role === "admin" || user?.role === "manager";

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) {
      setError("Choose a file to upload");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", title);
      form.append("doc_type", docType);
      form.append("department_id", departmentId);
      form.append("description", description);
      form.append("tags", JSON.stringify(tags.split(",").map((t) => t.trim()).filter(Boolean)));
      form.append("allowed_department_ids", JSON.stringify(allowedDepts));
      form.append("allowed_roles", JSON.stringify(allowedRoles));
      if (supersedeDocument) form.append("supersedes_document_id", supersedeDocument.id);

      const res = await api.post("/api/documents", form, { headers: { "Content-Type": "multipart/form-data" } });
      onUploaded(res.data);
    } catch (err) {
      setError(apiErrorMessage(err, "Upload failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={supersedeDocument ? `Upload new version: ${supersedeDocument.title}` : "Upload a document"} onClose={onClose} width="max-w-xl">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}

        <label className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-300 py-8 cursor-pointer hover:border-atlas-500 hover:bg-atlas-50/40 transition">
          <UploadCloud size={26} className="text-atlas-600" />
          <span className="text-sm text-slate-600">
            {file ? <span className="font-medium text-ink-900">{file.name}</span> : "Click to choose a file (PDF, DOCX, XLSX, PPTX, image, CSV)"}
          </span>
          <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>

        <div>
          <label className="label">Title</label>
          <input className="input" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Vendor Supply Agreement - XYZ Ltd" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Document type</label>
            <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Department</label>
            <select
              className="input"
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              disabled={!!supersedeDocument || !canPickAnyDepartment}
            >
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="label">Description (optional)</label>
          <textarea className="input" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div>
          <label className="label">Tags (comma separated, optional)</label>
          <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="ramanagara, vendor, urgent" />
        </div>

        {!supersedeDocument && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-3">
            <p className="text-xs font-semibold text-slate-500">EXTRA VIEWER ACCESS (optional)</p>
            <div>
              <label className="label">Also visible to these departments</label>
              <div className="flex flex-wrap gap-2">
                {departments.map((d) => (
                  <Chip key={d.id} active={allowedDepts.includes(d.id)} onClick={() => toggle(d.id, allowedDepts, setAllowedDepts)}>
                    {d.name}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <label className="label">Also visible to these roles, org-wide</label>
              <div className="flex flex-wrap gap-2">
                {ROLES.map((r) => (
                  <Chip key={r.value} active={allowedRoles.includes(r.value)} onClick={() => toggle(r.value, allowedRoles, setAllowedRoles)}>
                    {r.label}
                  </Chip>
                ))}
              </div>
            </div>
          </div>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy && <Loader2 size={16} className="animate-spin" />}
          {supersedeDocument ? "Upload new version" : "Upload document"}
        </button>
      </form>
    </Modal>
  );
}

function toggle(value, list, setList) {
  setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
}

function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-xs rounded-full px-3 py-1 border transition ${
        active ? "bg-atlas-700 text-white border-atlas-700" : "bg-white text-slate-600 border-slate-300 hover:border-atlas-400"
      }`}
    >
      {children}
    </button>
  );
}
