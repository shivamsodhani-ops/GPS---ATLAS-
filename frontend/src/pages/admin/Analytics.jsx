import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid } from "recharts";
import { FileText, Database, Users, AlertTriangle, Copy } from "lucide-react";
import { api } from "../../api/client";
import { formatBytes } from "../../utils/format";

const COLORS = ["#297052", "#5aa683", "#8bc5a9", "#b8ddca", "#183c2f", "#398a67", "#dbeee4"];

export default function Analytics() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/api/admin/analytics").then((res) => setData(res.data));
  }, []);

  if (!data) return <p className="text-slate-400 text-sm">Loading analytics…</p>;

  const byDept = Object.entries(data.documents_by_department).map(([name, value]) => ({ name, value }));
  const byType = Object.entries(data.documents_by_type).map(([name, value]) => ({ name, value }));
  const uploadsByDay = Object.entries(data.uploads_last_30_days).map(([date, value]) => ({
    date: date.slice(5),
    value,
  }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-ink-900">Analytics</h1>
        <p className="text-slate-500 mt-1 text-sm">An organization-wide view of what's stored in ATLAS and how it's used.</p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat icon={FileText} label="Documents" value={data.total_documents} sub={`${data.total_versions} versions tracked`} />
        <Stat icon={Database} label="Storage used" value={formatBytes(data.total_storage_bytes)} sub="encrypted at rest" />
        <Stat icon={Users} label="Active users (30d)" value={`${data.active_users_last_30_days}/${data.total_users}`} sub="logged in recently" />
        <Stat icon={AlertTriangle} label="Expiring soon" value={data.documents_expiring_soon.length} sub="within 60 days" tone={data.documents_expiring_soon.length ? "warn" : "default"} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card p-5">
          <h2 className="font-semibold text-ink-900 mb-4">Documents by department</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={byDept} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(e) => e.name}>
                {byDept.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-5">
          <h2 className="font-semibold text-ink-900 mb-4">Documents by type</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={byType} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#297052" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-5">
        <h2 className="font-semibold text-ink-900 mb-4">Uploads &amp; new versions (last 30 days)</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={uploadsByDay}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" fill="#5aa683" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        {uploadsByDay.length === 0 && <p className="text-sm text-slate-400 text-center">No uploads in the last 30 days.</p>}
      </div>

      {data.near_duplicate_flags > 0 && (
        <div className="card p-5 border-amber-200 bg-amber-50/40">
          <h2 className="font-semibold text-ink-900 mb-2 flex items-center gap-2">
            <Copy size={16} className="text-amber-600" /> {data.near_duplicate_flags} possible duplicate document{data.near_duplicate_flags === 1 ? "" : "s"} detected
          </h2>
          <p className="text-sm text-slate-600">
            ATLAS flags versions that look highly similar to something already in the depository, so the same
            contract or drawing doesn't end up scattered under two titles. Review these from the Document Library.
          </p>
        </div>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, sub, tone = "default" }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        <Icon size={16} className={tone === "warn" ? "text-amber-500" : "text-atlas-600"} />
      </div>
      <div className="text-2xl font-bold text-ink-900 mt-2">{value}</div>
      <div className="text-xs text-slate-400 mt-0.5">{sub}</div>
    </div>
  );
}
