import { highlightSql } from "../lib";

export default function QueryPreviewBox({ title, content }) {
  return (
    <section className="sql-section-block">
      <div className="sql-section-title">{title}</div>
      <div className="sql-output-box">
        <pre
          className="sql-preview"
          dangerouslySetInnerHTML={{
            __html: highlightSql(content || ""),
          }}
        />
      </div>
    </section>
  );
}
