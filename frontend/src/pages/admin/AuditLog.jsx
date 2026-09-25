import { useEffect, useState } from "react";
import { ShieldCheck, LogIn, Upload, Download, Search, Eye, Ban, UserCog, Building2 } from "lucide-react";
import { api } from "../../api/client";
import { formatDateTime } from "../../utils/format";

const ACTION_META = {
  login_success: { icon: LogIn, color: "text-emerald-600", label: "Signed in" },
  login_failure: { icon: Ban, color: "text-red-600", label: "Failed login" },
  logout: { icon: LogIn, color: "text-slate-400", label: "Signed out" },
  upload: { icon: Upload, color: "text-atlas-600", label: "Uploaded document" },
  new_version: { icon: Upload, color: "text-atlas-600", label: "Uploaded new version" },
  view_document: { icon: Eye, color: "text-slate-500", label: "Viewed document" },
  download_document: { icon: Download, color: "text-blue-600", label: "Downloaded document" },
  search: { icon: Search, color: "text-purple-600", label: "Searched / asked ATLAS" },
  access_denied: { icon: Ban, color: "text-red-600", label: "Access denied" },
  user_created: { icon: UserCog, color: "text-emerald-600", label: "User created" },
  user_updated: { icon: UserCog, color: "text-slate-500", label: "User updated" },
  user_deactivated: { icon: UserCog, color: "text-red-600", label: "User deactivated" },
  department_created: { icon: Building2, color: "text-emerald-600", label: "Department created" },
  document_archived: { icon: Ban, color: "text-amber-600", label: "Document archived" },
  access_grant_changed: { icon: ShieldCheck, color: "text-emerald-600", label: "Access grant changed" },
};

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [actionFilter, setActionFilter] = useState("");

  useEffect(() => {
    api.get("/api/admin/audit-logs", { params: actionFilter ? { action: actionFilter } : {} }).then((res) => setLogs(res.data));
  }, [actionFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Audit Log</h1>
          <p className="text-slate-500 mt-1 text-sm">Every login, upload, download, search and admin action — immutable and timestamped.</p>
        </div>
        <select className="input w-auto" value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
          <option value="">All actions</option>
          {Object.entries(ACTION_META).map(([key, meta]) => (
            <option key={key} value={key}>
              {meta.label}
            </option>
          ))}
        </select>
      </div>

      <div className="card divide-y divide-slate-100">
        {logs.map((log) => {
          const meta = ACTION_META[log.action] || { icon: ShieldCheck, color: "text-slate-500", label: log.action };
          const Icon = meta.icon;
          let detail = {};
          try {
            detail = JSON.parse(log.detail || "{}");
          } catch {
            /* ignore */
          }
          return (
            <div key={log.id} className="flex items-start gap-3 px-4 py-3">
              <Icon size={16} className={`${meta.color} mt-0.5 shrink-0`} />
              <div className="min-w-0 flex-1">
                <div className="text-sm text-ink-900">
                  <span className="font-medium">{log.user_name || "Unknown"}</span> {meta.label.toLowerCase()}
                  {log.document_title && (
                    <>
                      : <span className="font-medium">{log.document_title}</span>
                    </>
                  )}
                </div>
                {detail.question && <div className="text-xs text-slate-500 mt-0.5 italic">“{detail.question}”</div>}
                <div className="text-xs text-slate-400 mt-0.5">
                  {formatDateTime(log.created_at)} {log.ip_address && `· ${log.ip_address}`}
                </div>
              </div>
            </div>
          );
        })}
        {logs.length === 0 && <div className="p-8 text-center text-slate-400 text-sm">No activity recorded yet.</div>}
      </div>
    </div>
  );
}
