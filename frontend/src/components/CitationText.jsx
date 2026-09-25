// Renders answer text, turning [1] [2] ... markers into clickable badges
// that jump to (and highlight) the matching citation card below.
export default function CitationText({ text, onJump }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-line leading-relaxed text-[15px] text-ink-800">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const n = Number(match[1]);
          return (
            <button
              key={i}
              onClick={() => onJump?.(n)}
              className="inline-flex items-center justify-center align-super text-[10px] font-bold mx-0.5 h-4 min-w-4 px-1 rounded-full bg-atlas-100 text-atlas-800 hover:bg-atlas-200"
              title={`Jump to source ${n}`}
            >
              {n}
            </button>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </p>
  );
}
