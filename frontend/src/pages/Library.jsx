import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Plus, Filter } from "lucide-react";
import { api } from "../api/client";
import { DOC_TYPES } from "../constants";
import DocTypeIcon from "../components/DocTypeIcon";
import UploadModal from "../components/UploadModal";
import DocumentDrawer from "../components/DocumentDrawer";
import { timeAgo } from "../utils/format";

export default function Library() {
  const [params, setParams] = useSearchParams();
  const [docs, setDocs] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [q, setQ] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [supersedeDocument, setSupersedeDocument] = useState(null);
  const [loading, setLoading] = useState(true);

  const activeDocId = params.get("doc");

  function loadDocs() {
    setLoading(true);
    const query = {};
    if (deptFilter) query.department_id = deptFilter;
    if (typeFilter) query.doc_type = typeFilter;
    if (q) query.q = q;
    api
      .get("/api/documents", { params: query })
      .then((res) => setDocs(res.data))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    api.get("/api/departments").then((res) => setDepartments(res.data));
  }, []);

  useEffect(() => {
    const timeout = setTimeout(loadDocs, 250);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, deptFilter, typeFilter]);

  const typeCounts = useMemo(() => {
    const counts = {};
    docs.forEach((d) => (counts[d.doc_type] = (counts[d.doc_type] || 0) + 1));
    return counts;
  }, [docs]);

  function openDoc(id) {
    setParams({ doc: id });
  }
  function closeDoc() {
    params.delete("doc");
    setParams(params);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Document Library</h1>
          <p className="text-slate-500 mt-1 text-sm">{docs.length} document{docs.length === 1 ? "" : "s"} you're authorized to view</p>
        </div>
        <button onClick={() => setShowUpload(true)} className="btn-primary">
          <Plus size={16} /> Upload document
        </button>
      </div>

      <div className="flex flex-wrap gap-3 mb-5">
        <div className="flex-1 min-w-[240px] relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9" placeholder="Search by title..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className="input w-auto" value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)}>
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select className="input w-auto" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {DOC_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label} {typeCounts[t.value] ? `(${typeCounts[t.value]})` : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="card divide-y divide-slate-100">
        {loading && <div className="p-8 text-center text-slate-400 text-sm">Loading…</div>}
        {!loading && docs.length === 0 && (
          <div className="p-10 text-center text-slate-500 text-sm flex flex-col items-center gap-2">
            <Filter size={22} className="text-slate-300" />
            No documents match. Try clearing filters, or upload a new one.
          </div>
        )}
        {docs.map((d) => (
          <button key={d.id} onClick={() => openDoc(d.id)} className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50">
            <DocTypeIcon type={d.doc_type} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-ink-900 truncate">{d.title}</div>
              <div className="text-xs text-slate-500 truncate">
                {d.department_name} · uploaded by {d.uploader_name} · v{d.version_count} · updated {timeAgo(d.updated_at)}
              </div>
            </div>
            {d.expiry_date && <span className="badge bg-amber-100 text-amber-700 shrink-0">expires soon</span>}
            <span className="badge bg-slate-100 text-slate-600 shrink-0">{d.doc_type}</span>
          </button>
        ))}
      </div>

      {showUpload && (
        <UploadModal
          departments={departments}
          onClose={() => setShowUpload(false)}
          onUploaded={() => {
            setShowUpload(false);
            loadDocs();
          }}
        />
      )}

      {supersedeDocument && (
        <UploadModal
          departments={departments}
          supersedeDocument={supersedeDocument}
          onClose={() => setSupersedeDocument(null)}
          onUploaded={() => {
            setSupersedeDocument(null);
            loadDocs();
          }}
        />
      )}

      {activeDocId && (
        <DocumentDrawer
          documentId={activeDocId}
          onClose={closeDoc}
          onArchived={() => loadDocs()}
          onUploadNewVersion={(doc) => {
            closeDoc();
            setSupersedeDocument(doc);
          }}
        />
      )}
    </div>
  );
}
