export default function BadgeStrip({ achievements }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      {achievements.map((badge) => (
        <article
          key={badge.id}
          className={`rounded-2xl border px-4 py-4 ${
            badge.earned
              ? "border-signal-400/30 bg-signal-500/10 text-slate-100"
              : "border-white/10 bg-white/5 text-slate-400"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">{badge.label}</h3>
            <span className="font-mono text-[11px] uppercase tracking-[0.24em]">
              {badge.earned ? "earned" : "locked"}
            </span>
          </div>
          <p className="mt-2 text-sm">{badge.description}</p>
        </article>
      ))}
    </div>
  );
}
