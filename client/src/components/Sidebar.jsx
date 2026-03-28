import { Link, useLocation } from "react-router-dom";

import ProgressBar from "./ProgressBar";
import { getCategoryPath } from "../lib";

export default function Sidebar({ categories, stats, open, onClose }) {
  const location = useLocation();

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/60 transition lg:hidden ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-[320px] border-r border-white/10 bg-chrome-950/96 p-5 backdrop-blur-xl transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="panel rounded-3xl p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-signal-400/80">SQLi Lab</p>
          <h1 className="mt-3 text-3xl font-semibold text-white">Training Console</h1>
          <p className="mt-3 text-base text-slate-300">Safe simulation tracks for payload logic, response reading, and defensive SQL coding.</p>
        </div>

        <div className="mt-5 panel-soft rounded-3xl p-4">
          <div className="mb-3 flex items-center justify-between font-mono text-[11px] uppercase tracking-[0.2em] text-slate-400">
            <span>Overall Progress</span>
            <span>{stats?.completion_percent ?? 0}%</span>
          </div>
          <ProgressBar value={stats?.completion_percent ?? 0} />
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-slate-300">
            <div className="rounded-2xl bg-white/5 px-3 py-3">
              <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-slate-500">Solved</div>
              <div className="mt-2 text-xl font-semibold text-white">{stats?.solved_levels ?? 0}</div>
            </div>
            <div className="rounded-2xl bg-white/5 px-3 py-3">
              <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-slate-500">Categories</div>
              <div className="mt-2 text-xl font-semibold text-white">{stats?.completed_categories ?? 0}</div>
            </div>
          </div>
        </div>

        <nav className="mt-5 space-y-2">
          <Link
            to="/"
            className={`block rounded-2xl border px-4 py-3 text-sm transition ${
              location.pathname === "/"
                ? "border-signal-400/30 bg-signal-500/10 text-white"
                : "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"
            }`}
            onClick={onClose}
          >
            Dashboard
          </Link>
          {categories.map((category) => (
            <Link
              key={category.slug}
              to={getCategoryPath(category)}
              onClick={onClose}
              className={`block rounded-2xl border px-4 py-3 transition ${
                location.pathname.startsWith(`/lab/${category.slug}/`)
                  ? "border-signal-400/30 bg-signal-500/10 text-white"
                  : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-base font-semibold">{category.title}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {category.progress.solved}/{category.progress.total} levels
                  </div>
                </div>
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">{category.difficulty}</span>
              </div>
            </Link>
          ))}
        </nav>
      </aside>
    </>
  );
}
