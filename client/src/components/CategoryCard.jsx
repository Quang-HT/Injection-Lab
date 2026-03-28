import { Link } from "react-router-dom";

import { getCategoryPath } from "../lib";

export default function CategoryCard({ category }) {
  return (
    <article className="panel rounded-3xl p-5">
      <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-slate-400">SQL type</p>
      <h3 className="mt-3 text-2xl font-semibold text-slate-900">{category.title}</h3>
      <p className="mt-2 text-sm leading-7 text-slate-500">{category.summary}</p>
      <div className="mt-5 flex items-center justify-between gap-4">
        <span className="rounded-full bg-slate-100 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
          {category.progress.total} levels
        </span>
        <Link
          to={getCategoryPath(category)}
          className="rounded-full bg-slate-900 px-4 py-2 font-mono text-xs uppercase tracking-[0.22em] text-white transition hover:bg-slate-800"
        >
          Open
        </Link>
      </div>
    </article>
  );
}
