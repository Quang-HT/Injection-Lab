import { useState } from "react";

export default function FlagReward({ flag }) {
  const [copied, setCopied] = useState(false);

  async function copyFlag() {
    try {
      await navigator.clipboard.writeText(flag);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  if (!flag) {
    return null;
  }

  return (
    <section className="flag-panel panel rounded-3xl p-5 animate-flag-pulse">
      <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-signal-400/80">Flag Captured</p>
      <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h3 className="text-2xl font-semibold text-white">{flag}</h3>
          <p className="mt-2 text-sm text-slate-300">Flag revealed from predefined challenge metadata after the simulated objective was completed.</p>
        </div>
        <button
          type="button"
          onClick={copyFlag}
          className="rounded-full border border-signal-400/30 bg-signal-500/10 px-4 py-2 font-mono text-xs uppercase tracking-[0.24em] text-signal-300 transition hover:bg-signal-500/20"
        >
          {copied ? "Copied" : "Copy Flag"}
        </button>
      </div>
    </section>
  );
}
