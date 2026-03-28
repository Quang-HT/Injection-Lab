import CategoryCard from "../components/CategoryCard";
import { useAppContext } from "../context/AppContext";

export default function DashboardPage() {
  const { bootstrap, loading, error } = useAppContext();

  if (loading && !bootstrap) {
    return <div className="panel rounded-3xl p-8 text-lg text-slate-700">Loading training dashboard...</div>;
  }

  if (error && !bootstrap) {
    return <div className="panel rounded-3xl p-8 text-lg text-rose-500">{error}</div>;
  }

  return (
    <div className="space-y-8">
      <section className="panel rounded-[2rem] p-6 md:p-8">
        <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-slate-400">Simple mode</p>
        <h2 className="mt-3 max-w-3xl text-4xl font-semibold leading-tight text-slate-900 md:text-5xl">
          Chon tung loai SQL Injection va thu payload mo phong
        </h2>
        <p className="mt-4 max-w-3xl text-lg leading-8 text-slate-500">
          Giao dien da duoc rut gon: chi hien thi ten loi SQL, o input, va ket qua loi dac trung do simulator tra ve.
        </p>
      </section>

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {(bootstrap?.categories ?? []).map((category) => (
          <CategoryCard key={category.slug} category={category} />
        ))}
      </section>
    </div>
  );
}
