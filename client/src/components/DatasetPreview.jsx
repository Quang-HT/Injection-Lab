export default function DatasetPreview({ title, rows }) {
  if (!rows?.length) {
    return null;
  }

  const columns = Object.keys(rows[0]);

  return (
    <article className="panel-soft overflow-hidden rounded-3xl">
      <div className="border-b border-white/10 px-4 py-3">
        <h3 className="font-mono text-xs uppercase tracking-[0.28em] text-slate-300">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/10 text-left">
          <thead className="bg-white/5">
            <tr>
              {columns.map((column) => (
                <th key={column} className="px-4 py-3 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map((row, index) => (
              <tr key={`${title}-${index}`} className="text-sm text-slate-200">
                {columns.map((column) => (
                  <td key={column} className="px-4 py-3 font-mono">
                    {String(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
