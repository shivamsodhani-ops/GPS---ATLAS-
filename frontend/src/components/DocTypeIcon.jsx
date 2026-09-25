import { FileText, FileSpreadsheet, Image, FileSignature, ClipboardList, Presentation, File } from "lucide-react";

const MAP = {
  contract: { icon: FileSignature, color: "text-purple-600 bg-purple-50" },
  purchase_order: { icon: FileSpreadsheet, color: "text-blue-600 bg-blue-50" },
  progress_report: { icon: ClipboardList, color: "text-emerald-600 bg-emerald-50" },
  mom: { icon: FileText, color: "text-amber-600 bg-amber-50" },
  drawing: { icon: Image, color: "text-pink-600 bg-pink-50" },
  policy: { icon: FileText, color: "text-slate-600 bg-slate-100" },
  datasheet: { icon: FileSpreadsheet, color: "text-cyan-600 bg-cyan-50" },
  deck: { icon: Presentation, color: "text-orange-600 bg-orange-50" },
};

export default function DocTypeIcon({ type }) {
  const entry = MAP[type] || { icon: File, color: "text-slate-500 bg-slate-100" };
  const Icon = entry.icon;
  return (
    <div className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${entry.color}`}>
      <Icon size={16} />
    </div>
  );
}
