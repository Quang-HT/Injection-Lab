import { Link, useLocation } from "react-router-dom";

import { getCategoryNavLabel, getCategoryPath } from "../lib";

export default function TopNav({ categories }) {
  const location = useLocation();

  return (
    <header className="sql-topbar">
      <div className="sql-topbar-inner">
        <Link to="/" className="sql-brand">
          <span className="sql-brand-mark" aria-hidden="true">
            HUCE - SEC
          </span>
          <span className="sql-brand-title">SQL Injection Visualization</span>
        </Link>

        <nav className="sql-top-nav">
          <Link to="/" className={location.pathname === "/" ? "sql-nav-link active" : "sql-nav-link"}>
            Console
          </Link>
          {categories.map((category) => (
            <Link
              key={category.slug}
              to={getCategoryPath(category)}
              className={location.pathname.startsWith(`/lab/${category.slug}/`) ? "sql-nav-link active" : "sql-nav-link"}
            >
              {getCategoryNavLabel(category)}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
