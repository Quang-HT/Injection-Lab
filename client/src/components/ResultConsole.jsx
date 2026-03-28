export default function ResultConsole({ title = "Kết quả:", content, compact = false, tone = "default" }) {
  const boxClassName = ["sql-result-box", compact ? "compact" : "", tone === "flag" ? "flag" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <section className="sql-section-block">
      <div className="sql-section-title">{title}</div>
      <div className={boxClassName}>
        <pre className="sql-result">{content || ""}</pre>
      </div>
    </section>
  );
}
