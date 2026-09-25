import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Search, Loader2, ShieldCheck, ShieldAlert, ExternalLink, Sparkles, AlertTriangle } from "lucide-react";
import { api, apiErrorMessage } from "../api/client";
import CitationText from "../components/CitationText";
import { formatDate } from "../utils/format";

const PROVIDER_LABEL = {
  extractive: "Extractive (offline, zero hallucination)",
  ollama: "Local model (Ollama)",
  hosted: "Hosted AI model",
};

export default function Ask() {
  const location = useLocation();
  const [question, setQuestion] = useState(location.state?.prefill || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [turns, setTurns] = useState([]);
  const bottomRef = useRef(null);
  const citationRefs = useRef({});

  useEffect(() => {
    if (location.state?.prefill) {
      handleAsk(location.state.prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length]);

  async function handleAsk(q) {
    const text = (q ?? question).trim();
    if (!text || busy) return;
    setError("");
    setBusy(true);
    setQuestion("");
    try {
      const res = await api.post("/api/ask", { question: text });
      setTurns((t) => [...t, { question: text, ...res.data }]);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not get an answer"));
    } finally {
      setBusy(false);
    }
  }

  function jumpTo(turnIdx, marker) {
    const el = citationRefs.current[`${turnIdx}-${marker}`];
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    el?.classList.add("ring-2", "ring-atlas-500");
    setTimeout(() => el?.classList.remove("ring-2", "ring-atlas-500"), 1500);
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-3xl mx-auto">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-ink-900 flex items-center gap-2">
          <Sparkles size={22} className="text-atlas-600" /> Ask ATLAS
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Answers are built only from documents you're authorized to view, and every claim is tagged with a
          clickable source.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-6 pb-4 pr-1">
        {turns.length === 0 && !busy && (
          <div className="card p-8 text-center text-slate-500">
            <Search size={28} className="mx-auto mb-3 text-slate-300" />
            Try: <span className="italic">“What's the delivery timeline in the BioCNG compressor supply agreement?”</span>
          </div>
        )}

        {turns.map((turn, idx) => (
          <div key={idx} className="space-y-3">
            <div className="flex justify-end">
              <div className="bg-atlas-700 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[85%] text-sm font-medium">
                {turn.question}
              </div>
            </div>

            <div className="card p-5">
              <CitationText text={turn.answer} onJump={(m) => jumpTo(idx, m)} />

              <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                <span className="badge bg-slate-100 text-slate-600">
                  Searched {turn.searched_document_count} authorized document{turn.searched_document_count === 1 ? "" : "s"}
                </span>
                <span className="badge bg-atlas-50 text-atlas-700">
                  {PROVIDER_LABEL[turn.provider_used] || turn.provider_used}
                </span>
                {turn.unverified_claims.length > 0 && (
                  <span className="badge bg-amber-100 text-amber-700">
                    <AlertTriangle size={12} /> {turn.unverified_claims.length} unverified statement
                    {turn.unverified_claims.length === 1 ? "" : "s"} flagged
                  </span>
                )}
              </div>

              {turn.unverified_claims.length > 0 && (
                <div className="mt-3 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
                  <div className="font-semibold mb-1">Not backed by a citation — verify independently:</div>
                  <ul className="list-disc list-inside space-y-0.5">
                    {turn.unverified_claims.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              {turn.citations.length > 0 && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <div className="text-xs font-semibold text-slate-500 mb-2">SOURCES</div>
                  <div className="space-y-2">
                    {turn.citations.map((c) => (
                      <div
                        key={c.marker}
                        ref={(el) => (citationRefs.current[`${idx}-${c.marker.replace(/\D/g, "")}`] = el)}
                        className="rounded-lg border border-slate-200 p-3 transition"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-2 min-w-0">
                            <span className="badge bg-atlas-100 text-atlas-800 mt-0.5">{c.marker}</span>
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-ink-900 truncate">{c.document_title}</div>
                              <div className="text-xs text-slate-500 mt-0.5">
                                {c.page_number ? `Page ${c.page_number} · ` : ""}
                                {c.verified ? (
                                  <span className="text-emerald-600 inline-flex items-center gap-1">
                                    <ShieldCheck size={11} /> used in the answer above
                                  </span>
                                ) : (
                                  <span className="text-slate-400 inline-flex items-center gap-1">
                                    <ShieldAlert size={11} /> retrieved, not directly quoted
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-slate-600 mt-1.5 line-clamp-2">{c.snippet}</p>
                            </div>
                          </div>
                          <a
                            href={`${api.defaults.baseURL}/api/documents/${c.document_id}/download`}
                            onClick={(e) => downloadWithAuth(e, c.document_id)}
                            className="shrink-0 text-atlas-700 hover:text-atlas-900"
                            title="Open source document"
                          >
                            <ExternalLink size={15} />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="flex items-center gap-2 text-sm text-slate-500 px-1">
            <Loader2 size={15} className="animate-spin" /> Searching authorized documents and verifying citations…
          </div>
        )}
        {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk();
        }}
        className="card p-2 flex items-center gap-2 mt-2"
      >
        <Search size={18} className="text-slate-400 ml-2" />
        <input
          className="flex-1 py-2.5 outline-none text-sm"
          placeholder="Ask a question about anything you're authorized to see..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="btn-primary" disabled={busy}>
          {busy ? <Loader2 size={15} className="animate-spin" /> : "Ask"}
        </button>
      </form>
      <p className="text-[11px] text-slate-400 mt-2 text-center">
        GPS ATLAS answers only from documents your Viewer ID authorizes — last updated {formatDate(new Date())}
      </p>
    </div>
  );
}

async function downloadWithAuth(e, documentId) {
  e.preventDefault();
  const res = await api.get(`/api/documents/${documentId}/download`, { responseType: "blob" });
  const disposition = res.headers["content-disposition"] || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "document";
  const url = window.URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}
