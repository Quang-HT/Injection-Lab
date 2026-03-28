from __future__ import annotations

from .sql_sandbox import SandboxRuntimeError, SandboxSqlError, execute_sql_sandbox


def normalize_query(query: str) -> str:
    compact = " ".join((query or "").strip().split())
    return compact[:-1] if compact.endswith(";") else compact


def format_value(value) -> str:
    if value is None:
        return "NULL"
    return str(value)


def build_ascii_table(rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "Total: 0 row(s)"

    widths: dict[str, int] = {}
    for column in columns:
        widths[column] = max(len(column), *(len(format_value(row.get(column))) for row in rows))

    border = "+" + "+".join("-" * (widths[column] + 2) for column in columns) + "+"
    lines = [f"Total: {len(rows)} row(s)", border]

    for row in rows:
        lines.append("| " + " | ".join(format_value(row.get(column)).ljust(widths[column]) for column in columns) + " |")
        lines.append(border)

    return "\n".join(lines)


def build_sql_error(error: Exception) -> str:
    if isinstance(error, SandboxRuntimeError):
        return f"SQL ERROR {error.code} ({error.sqlstate}): {error}"
    return f"SQL ERROR 1064 (42000): {error}"


def execute_console_query(query: str) -> dict:
    query_length = len(query or "")
    normalized = normalize_query(query)

    if not normalized:
        return {
            "query": "",
            "query_length": query_length,
            "result": "Nhap mot cau truy van SQL de bat dau.",
            "status": "idle",
        }

    try:
        result = execute_sql_sandbox(normalized)
    except (SandboxSqlError, SandboxRuntimeError) as error:
        return {
            "query": f"{normalized};",
            "query_length": query_length,
            "result": build_sql_error(error),
            "status": "error",
        }

    rows = result["rows"]
    if rows:
        columns = list(rows[0].keys())
        rendered_result = build_ascii_table(rows, columns)
    else:
        last_statement = result["statements"][-1].lower() if result["statements"] else ""
        if last_statement.startswith(("insert ", "update ", "delete ", "drop table ")):
            rendered_result = "Query OK, 0 row(s) in result set"
        else:
            rendered_result = "Total: 0 row(s)"

    return {
        "query": f"{normalized};",
        "query_length": query_length,
        "result": rendered_result,
        "status": "ok",
    }
