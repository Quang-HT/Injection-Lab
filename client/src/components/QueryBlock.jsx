import { highlightSql } from "../lib";

export default function QueryBlock({ title, query, tone = "default" }) {
  const toneClass =
    tone === "unsafe"
      ? "border-threat-400/20 bg-threat-500/5"
      : "border-signal-400/20 bg-signal-500/5";

  return (
    <article className={`rounded-3xl border p-4 ${toneClass}`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-mono text-xs uppercase tracking-[0.3em] text-slate-300">{title}</h3>
        <span className="rounded-full border border-white/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-slate-400">
          pseudo sql
        </span>
      </div>
      <pre className="sql-block overflow-x-auto rounded-2xl bg-black/30 p-4 text-sm leading-7 text-slate-100 glow-outline">
        <code dangerouslySetInnerHTML={{ __html: highlightSql(query) }} />
      </pre>
    </article>
  );
}
