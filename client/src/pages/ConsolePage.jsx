import { useEffect, useState } from "react";

import { executeConsoleQuery } from "../api";
import FooterNote from "../components/FooterNote";
import QueryPreviewBox from "../components/QueryPreviewBox";
import ResultConsole from "../components/ResultConsole";

export default function ConsolePage() {
  const [query, setQuery] = useState("SELECT 1337;");
  const [consoleResult, setConsoleResult] = useState({
    query: "SELECT 1337;",
    query_length: 12,
    result: "Total: 1 row(s)\n+------+\n| 1337 |\n+------+",
    status: "ok",
  });
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const result = await executeConsoleQuery(query);
        setConsoleResult(result);
        setError("");
      } catch (requestError) {
        setError(requestError.message);
      }
    }, 220);

    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <div className="sql-page">
      <section className="sql-page-head">
        <div className="sql-hero-icon" />
        <h1 className="sql-page-title">Interactive SQL Console</h1>
      </section>

      <section className="sql-workarea">
        <div className="sql-label">
          SQL query <span className="sql-length">(length: {query.length})</span>
        </div>

        <textarea
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="sql-input sql-console-input"
          spellCheck={false}
        />

        <div className="sql-divider" />

        <QueryPreviewBox title="Câu Query:" content={consoleResult.query || query} />
        <ResultConsole title="Kết quả:" content={error || consoleResult.result} />
      </section>

      <FooterNote />
    </div>
  );
}
