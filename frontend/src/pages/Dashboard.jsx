import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, FileText, Clock, AlertTriangle, ArrowRight } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import DocTypeIcon from "../components/DocTypeIcon";
import { timeAgo } from "../utils/format";

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [docs, setDocs] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.get("/api/documents").then((res) => setDocs(res.data));
    if (user?.role === "admin" || user?.role === "manager") {
      api.get("/api/admin/analytics").then((res) => setAnalytics(res.data)).catch(() => {});
    }
  }, [user]);

  function submitAsk(e) {
    e.preventDefault();
    if (!query.trim()) return;
    navigate("/ask", { state: { prefill: query } });
  }

  const recent = docs.slice(0, 6);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-ink-900">Welcome back, {user?.name?.split(" ")[0]}</h1>
        <p className="text-slate-500 mt-1">
          {docs.length} document{docs.length === 1 ? "" : "s"} available to you across GPS.
        </p>
      </div>

      <form onSubmit={submitAsk} className="card p-2 flex items-center gap-2">
        <Search size={18} className="text-slate-400 ml-2" />
        <input
          className="flex-1 py-2.5 outline-none text-sm"
          placeholder="Ask ATLAS anything — e.g. &quot;What's the penalty clause in the BioCNG supply agreement?&quot;"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn-primary">
          Ask <ArrowRight size={15} />
        </button>
      </form>

      {analytics && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Documents" value={analytics.total_documents} icon={FileText} />
          <StatCard label="Versions tracked" value={analytics.total_versions} icon={Clock} />
          <StatCard
            label="Expiring within 60 days"
            value={analytics.documents_expiring_soon.length}
            icon={AlertTriangle}
            tone={analytics.documents_expiring_soon.length > 0 ? "warn" : "default"}
          />
          <StatCard label="Possible duplicates" value={analytics.near_duplicate_flags} icon={AlertTriangle} tone={analytics.near_duplicate_flags > 0 ? "warn" : "default"} />
        </div>
      )}

      {analytics && analytics.documents_expiring_soon.length > 0 && (
        <div className="card p-5">
          <h2 className="font-semibold text-ink-900 mb-3 flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-500" /> Documents expiring soon
          </h2>
          <div className="divide-y divide-slate-100">
            {analytics.documents_expiring_soon.slice(0, 5).map((d) => (
              <div key={d.document_id} className="py-2 flex items-center justify-between text-sm">
                <button className="text-left hover:text-atlas-700 font-medium" onClick={() => navigate(`/library?doc=${d.document_id}`)}>
                  {d.title}
                </button>
                <span className={`badge ${d.days_remaining < 14 ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>
                  {d.days_remaining} day{d.days_remaining === 1 ? "" : "s"} left · {d.source}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-ink-900">Recently updated documents</h2>
          <button onClick={() => navigate("/library")} className="text-sm text-atlas-700 font-medium hover:underline">
            View library
          </button>
        </div>
        <div className="divide-y divide-slate-100">
          {recent.map((d) => (
            <button
              key={d.id}
              onClick={() => navigate(`/library?doc=${d.id}`)}
              className="w-full flex items-center gap-3 py-3 text-left hover:bg-slate-50 -mx-2 px-2 rounded-lg"
            >
              <DocTypeIcon type={d.doc_type} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink-900 truncate">{d.title}</div>
                <div className="text-xs text-slate-500">
                  {d.department_name} · v{d.version_count} · {timeAgo(d.updated_at)}
                </div>
              </div>
              <span className="badge bg-slate-100 text-slate-600">{d.doc_type}</span>
            </button>
          ))}
          {recent.length === 0 && <p className="text-sm text-slate-500 py-6 text-center">No documents yet. Upload your first one from the Library.</p>}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tone = "default" }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        <Icon size={16} className={tone === "warn" ? "text-amber-500" : "text-atlas-600"} />
      </div>
      <div className="text-2xl font-bold text-ink-900 mt-2">{value}</div>
    </div>
  );
}
