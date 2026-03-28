from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import unquote_plus

from ..data.mock_data import get_dataset
from .sql_sandbox import (
    SandboxRuntimeError,
    SandboxSqlError,
    execute_sql_sandbox,
    get_sandbox_datasets,
    reconstruct_fragmented_keywords,
    render_query_template,
)


SESSION_STATE: dict[tuple[str, str], dict[str, Any]] = {}
FLAG_PATTERN = re.compile(r"HCSC\{[^}\r\n]+\}")


def reset_challenge_state(user_id: str, challenge_id: str) -> None:
    SESSION_STATE.pop((user_id, challenge_id), None)


def get_challenge_state(user_id: str, challenge_id: str) -> dict[str, Any]:
    return SESSION_STATE.setdefault((user_id, challenge_id), {})


def normalize(value: str) -> str:
    return unquote_plus((value or "").strip()).lower()


def decode_input_value(raw_value: str, passes: int) -> str:
    value = raw_value or ""
    for _ in range(max(passes, 0)):
        value = unquote_plus(value)
    return value


def materialize_query_inputs(challenge: dict, inputs: dict[str, str]) -> dict[str, str]:
    simulation = challenge.get("simulation", {})
    variant = simulation.get("filter_variant") or simulation.get("variant")
    decode_passes = 0
    if variant in {
        "block_quote",
        "block_quote_comment",
        "block_quote_doublequote",
        "block_comment",
        "block_or_keyword",
        "block_select_keyword",
        "block_union_keyword",
        "regex_filter",
        "login_blacklist",
        "case_sensitive_filter",
        "space_filter",
    }:
        decode_passes = 1
    if variant == "waf_filter":
        decode_passes = 2
    if variant == "login_waf":
        decode_passes = 2
    if variant == "encode_filter":
        decode_passes = 2
    if variant == "advanced_parser":
        decode_passes = 2

    materialized: dict[str, str] = {}
    for key, value in inputs.items():
        if key in {"password", "trigger_action", "fix"}:
            materialized[key] = value
        else:
            materialized[key] = decode_input_value(value, decode_passes)
    return materialized


def canonicalize_sql(
    raw_value: str,
    *,
    decode_passes: int = 1,
    strip_comments: bool = False,
    expand_version_comments: bool = False,
) -> str:
    value = raw_value or ""
    for _ in range(max(decode_passes, 0)):
        value = unquote_plus(value)

    value = reconstruct_fragmented_keywords(value)

    if expand_version_comments:
        value = re.sub(
            r"/\*!\d*\s*([a-z0-9_]+)\s*\*/",
            lambda match: f" {match.group(1)} ",
            value,
            flags=re.IGNORECASE,
        )

    if strip_comments:
        value = re.sub(r"/\*(?!\!)(.*?)\*/", " ", value, flags=re.DOTALL)
        value = re.sub(r"--.*$", " ", value, flags=re.MULTILINE)
        value = re.sub(r"#.*$", " ", value, flags=re.MULTILINE)
    else:
        value = re.sub(r"/\*(.*?)\*/", " ", value, flags=re.DOTALL)

    value = re.sub(r"\s+", " ", value).strip()
    return value.lower()


def has_tautology_expression(raw_value: str) -> bool:
    normalized = canonicalize_sql(raw_value)
    if re.search(r"\b1\s*=\s*1\b", normalized):
        return True
    if re.search(r"\b(\d+)\s*=\s*\1\b", normalized):
        return True
    if re.search(r"\bor\s+true\b", normalized):
        return True
    if re.search(r"'([^']+)'\s*=\s*'\1'", raw_value, flags=re.IGNORECASE):
        return True
    return False


def has_union_semantics(raw_value: str) -> bool:
    semantic = canonicalize_sql(raw_value, decode_passes=2, expand_version_comments=True)
    return "union" in semantic and "select" in semantic


def find_user_by_username(username: str) -> dict[str, Any] | None:
    for user in get_dataset("users"):
        if user["username"].lower() == username.lower():
            return user
    return None


def pick_first_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def get_query_tail(unsafe_query: str) -> str:
    if "..." in (unsafe_query or ""):
        return unsafe_query.split("...", 1)[1].strip()
    return unsafe_query


def find_flag_tokens(value: Any) -> list[str]:
    return FLAG_PATTERN.findall(str(value or ""))


def extract_flags_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    matches: list[str] = []
    for row in rows or []:
        for value in row.values():
            matches.extend(find_flag_tokens(value))
    return matches


def row_matches(row: dict[str, Any], **criteria: Any) -> bool:
    for key, value in criteria.items():
        current = row.get(key)
        if isinstance(current, str) or isinstance(value, str):
            if str(current or "").lower() != str(value or "").lower():
                return False
        elif current != value:
            return False
    return True


def find_flag_row(category_slug: str) -> dict[str, Any] | None:
    for row in get_dataset("flags"):
        if row_matches(row, category=category_slug):
            return row
    return None


def get_expected_flag(challenge: dict) -> str | None:
    category_slug = challenge.get("category_slug")
    if category_slug == "login-bypass":
        admin_user = find_user_by_username("admin")
        if admin_user:
            return admin_user.get("flag")
        return None
    if category_slug == "second-order-classic":
        for dataset_name in ("admin_notes", "hidden_messages"):
            for row in get_dataset(dataset_name):
                flag = row.get("flag")
                if flag:
                    return str(flag)
        return None

    row = find_flag_row(category_slug or "")
    if row:
        return str(row.get("flag") or "")
    return challenge.get("flag")


def payload_mentions_flag(payload: str, expected_flag: str | None) -> bool:
    if not expected_flag:
        return False
    return expected_flag.lower() in canonicalize_sql(payload, decode_passes=2)


def lines_contain_flag(lines: list[str], expected_flag: str | None) -> bool:
    if not expected_flag:
        return False
    return any(expected_flag in line for line in lines)


def rows_contain_flag(rows: list[dict[str, Any]], expected_flag: str | None) -> bool:
    if not expected_flag:
        return False
    return expected_flag in extract_flags_from_rows(rows)


def run_query_template(
    challenge: dict,
    inputs: dict[str, str],
    *,
    query_override: str | None = None,
    variables: dict[str, Any] | None = None,
    datasets: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[str, dict[str, Any]]:
    rendered_query = render_query_template(
        query_override or challenge.get("unsafe_query", ""),
        materialize_query_inputs(challenge, inputs),
    )
    result = execute_sql_sandbox(
        rendered_query,
        datasets=datasets or get_sandbox_datasets(),
        variables=variables,
    )
    return rendered_query, result


def build_db_error_lines(error: Exception) -> list[str]:
    if isinstance(error, SandboxRuntimeError):
        return [f"[db] SQL ERROR {error.code} ({error.sqlstate}): {error}"]
    return [f"[db] SQL ERROR 1064 (42000): {error}"]


def apply_filter_variant(payload_raw: str, variant: str) -> tuple[bool, list[str]]:
    raw = payload_raw or ""
    decoded_once = canonicalize_sql(raw, decode_passes=1)
    decoded_twice = canonicalize_sql(raw, decode_passes=2)
    strict_scan = canonicalize_sql(raw, decode_passes=1, strip_comments=True, expand_version_comments=True)
    trace = [f"Variant: {variant}"]

    if variant == "no_filter":
        trace.append("Rule: no filter applied.")
        return False, trace

    if variant == "block_quote":
        blocked = "'" in raw
        trace.append("Rule: block single quote.")
        return blocked, trace

    if variant == "block_quote_comment":
        blocked = "'" in raw or "--" in raw
        trace.append("Rule: block single quote and double dash comment.")
        return blocked, trace

    if variant == "block_quote_doublequote":
        blocked = "'" in raw or '"' in raw
        trace.append("Rule: block single and double quotes.")
        return blocked, trace

    if variant == "block_comment":
        blocked = "--" in raw or "#" in raw or "/*" in raw
        trace.append("Rule: block SQL comment markers.")
        return blocked, trace

    if variant == "block_or_keyword":
        blocked = bool(re.search(r"\bor\b", raw, flags=re.IGNORECASE))
        trace.append("Rule: block keyword OR.")
        return blocked, trace

    if variant == "block_select_keyword":
        blocked = bool(re.search(r"select", raw, flags=re.IGNORECASE))
        trace.append("Rule: block keyword SELECT.")
        return blocked, trace

    if variant == "block_union_keyword":
        blocked = bool(re.search(r"union", raw, flags=re.IGNORECASE))
        trace.append("Rule: block keyword UNION.")
        return blocked, trace

    if variant == "regex_filter":
        blocked = bool(re.search(r"union\s+select|or\s+1\s*=\s*1|--|'|/\*", raw, flags=re.IGNORECASE))
        trace.append("Rule: regex block on union select, tautology, quotes, and comments.")
        return blocked, trace

    if variant == "waf_filter":
        blocked = any(token in strict_scan for token in ("union select", "sleep(", "benchmark("))
        trace.append("Rule: decode once, strip comments, and block common SQLi signatures.")
        return blocked, trace

    if variant == "encode_filter":
        blocked = any(token in decoded_once for token in ("union", "select", "--", "'"))
        trace.append("Rule: decode once before filtering.")
        trace.append(f"Decoded once: {decoded_once}")
        trace.append(f"Decoded twice: {decoded_twice}")
        return blocked, trace

    if variant == "case_sensitive_filter":
        blocked = "UNION" in raw or "SELECT" in raw
        trace.append("Rule: block only uppercase UNION and SELECT.")
        return blocked, trace

    if variant == "space_filter":
        blocked = " " in raw
        trace.append("Rule: block literal spaces.")
        return blocked, trace

    if variant == "advanced_parser":
        blocked = "union select" in strict_scan or "'" in strict_scan or has_tautology_expression(raw)
        trace.append("Rule: decode once, strip normal comments, detect canonical tokens.")
        return blocked, trace

    if variant == "login_blacklist":
        blocked = bool(
            re.search(
                r"'|\"|\bor\b|\bunion\b|\bselect\b|--|/\*| ",
                raw,
                flags=re.IGNORECASE,
            )
        )
        trace.append("Rule: blacklist common SQLi tokens and literal spaces.")
        return blocked, trace

    if variant == "login_waf":
        blocked = any(token in strict_scan for token in (" or ", " union ", " select ", "'", '"'))
        trace.append("Rule: decode once, strip comments, then block common login-bypass signatures.")
        trace.append(f"Decoded once canonical: {strict_scan}")
        return blocked, trace

    trace.append("Rule: unknown filter variant, default allow.")
    return False, trace


def build_result(
    solved: bool,
    headline: str,
    terminal: list[str],
    explanation: str,
    *,
    status: str = "retry",
    mock_rows: list[dict] | None = None,
    boolean_result: bool | None = None,
    delay_ms: int = 0,
    query_log: list[str] | None = None,
    filter_trace: list[str] | None = None,
    state_message: str | None = None,
    display_message: str | None = None,
    flag: str | None = None,
) -> dict:
    return {
        "solved": solved,
        "status": "success" if solved else status,
        "headline": headline,
        "terminal": terminal,
        "explanation": explanation,
        "mock_rows": mock_rows or [],
        "boolean_result": boolean_result,
        "delay_ms": delay_ms,
        "query_log": query_log or [],
        "filter_trace": filter_trace or [],
        "state_message": state_message,
        "display_message": display_message or "",
        "flag": flag,
    }


def strip_login_tokens(value: str, tokens: list[str], *, decode_passes: int = 0) -> str:
    cleaned = decode_input_value(value, decode_passes)
    for token in tokens:
        cleaned = re.sub(re.escape(token), "", cleaned, flags=re.IGNORECASE)
    return cleaned


def prepare_login_inputs(username_raw: str, password_raw: str, variant: str) -> tuple[bool, dict[str, str], list[str]]:
    username = username_raw or ""
    password = password_raw or ""
    trace = [f"Variant: {variant}"]
    blocked = False

    if variant == "login_round_1":
        trace.append("Rule: strip token 'or' from username before rendering the query.")
        cleaned = strip_login_tokens(username, ["or"])
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "login_round_2":
        trace.append("Rule: strip tokens or, and, like, =, -- from username.")
        cleaned = strip_login_tokens(username, ["or", "and", "like", "=", "--"])
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "login_round_3":
        trace.append("Rule: strip tokens or, and, =, like, >, <, --, /*, */ from username.")
        cleaned = strip_login_tokens(username, ["or", "and", "=", "like", ">", "<", "--", "/*", "*/"])
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "login_round_4":
        trace.append("Rule: strip tokens or, and, =, like, >, <, --, /*, */, admin from username.")
        cleaned = strip_login_tokens(username, ["or", "and", "=", "like", ">", "<", "--", "/*", "*/", "admin"])
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "login_round_5":
        trace.append("Rule: strip tokens or, and, =, like, >, <, --, /*, */, admin, union from username.")
        cleaned = strip_login_tokens(username, ["or", "and", "=", "like", ">", "<", "--", "/*", "*/", "admin", "union"])
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "login_round_6":
        trace.append("Rule: strip tokens or, and, true, false, union, like, =, >, <, ;, --, /*, */, admin from username.")
        cleaned = strip_login_tokens(
            username,
            ["or", "and", "true", "false", "union", "like", "=", ">", "<", ";", "--", "/*", "*/", "admin"],
        )
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "login_round_7":
        trace.append("Rule: URL-decode once, then strip tokens or, and, true, false, union, like, =, >, <, ;, --, /*, */, admin.")
        cleaned = strip_login_tokens(
            username,
            ["or", "and", "true", "false", "union", "like", "=", ">", "<", ";", "--", "/*", "*/", "admin"],
            decode_passes=1,
        )
        return blocked, {"username": cleaned, "password": decode_input_value(password, 1)}, trace

    if variant == "no_filter":
        trace.append("Rule: no filter applied.")
        return blocked, {"username": username, "password": password}, trace

    if variant == "space_strip_filter":
        trace.append("Rule: backend strips literal spaces from username.")
        return blocked, {"username": username.replace(" ", ""), "password": password}, trace

    if variant == "logical_filter_strip":
        trace.append("Rule: backend removes OR/AND non-recursively from username.")
        cleaned = re.sub(r"OR|AND", "", username, flags=re.IGNORECASE)
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "equality_filter_strip":
        trace.append("Rule: backend strips '=' from username.")
        return blocked, {"username": username.replace("=", ""), "password": password}, trace

    if variant == "quote_escape_filter":
        trace.append("Rule: quote escaping still leaves room for a trailing backslash trick.")
        return blocked, {"username": username, "password": password}, trace

    if variant == "comment_filter_strip":
        trace.append("Rule: backend strips --, #, /*, */ from username.")
        cleaned = re.sub(r"--|#|/\*|\*/", "", username)
        return blocked, {"username": cleaned, "password": password}, trace

    if variant == "case_sensitive_or_strip":
        trace.append("Rule: backend strips only lowercase 'or'.")
        return blocked, {"username": username.replace("or", ""), "password": password}, trace

    if variant == "non_recursive_or_filter":
        trace.append("Rule: backend runs a single non-recursive OR replacement.")
        return blocked, {"username": username.replace("OR", ""), "password": password}, trace

    if variant == "string_char_filter":
        blocked = "admin" in username.lower()
        trace.append("Rule: direct alphabetic target tokens like 'admin' are blocked, hex-style comparisons remain.")
        return blocked, {"username": username, "password": password}, trace

    if variant == "login_waf_signature":
        blocked = bool(re.search(r"'|\bOR\b|\bUNION\b|\bSELECT\b", username, flags=re.IGNORECASE))
        trace.append("Rule: WAF checks raw plain-text signatures before the server URL-decodes once.")
        trace.append(f"Raw payload inspected: {username}")
        return blocked, {"username": decode_input_value(username, 1), "password": decode_input_value(password, 1)}, trace

    if variant == "hpp_override":
        pieces = username.split("&user=")
        first_piece = pieces[0]
        last_piece = pieces[-1]
        trace.append(f"Rule: WAF inspected first user={first_piece!r}; backend kept last user={last_piece!r}.")
        return blocked, {"username": last_piece, "password": password}, trace

    if variant == "strict_logical_block":
        blocked = bool(re.search(r"\bOR\b|\bAND\b|\|\||&&", username, flags=re.IGNORECASE))
        trace.append("Rule: strict regex blocks OR, AND, ||, &&.")
        return blocked, {"username": username, "password": password}, trace

    if variant == "space_comment_block":
        blocked = bool(re.search(r"\s|--|#|/\*", username))
        trace.append("Rule: spaces and comment markers are blocked together.")
        return blocked, {"username": username, "password": password}, trace

    if variant == "null_byte_filter":
        visible_prefix = username.split("%00", 1)[0].split("\x00", 1)[0]
        trace.append(f"Rule: validator only sees the prefix before null byte -> {visible_prefix!r}.")
        return blocked, {"username": decode_input_value(username, 1), "password": password}, trace

    blocked, trace = apply_filter_variant(username_raw, variant)
    return blocked, {"username": username, "password": password}, trace


def normalize_login_query(query: str) -> str:
    normalized = query or ""
    normalized = re.sub(r"\|\|", " OR ", normalized)
    normalized = re.sub(r"\bXOR\b", " OR ", normalized, flags=re.IGNORECASE)
    return normalized


def simulate(challenge: dict, inputs: dict[str, str], user_id: str) -> dict:
    simulation_type = challenge["simulation"]["type"]
    state = get_challenge_state(user_id, challenge["id"])

    evaluators = {
        "login_flow": simulate_login_flow,
        "product_union": simulate_product_union,
        "error_syntax": simulate_error_syntax,
        "error_extract": simulate_error_extract,
        "boolean_blind": simulate_boolean_blind,
        "time_blind": simulate_time_blind,
        "stacked_query": simulate_stacked_query,
        "second_order": lambda current, form_inputs: simulate_second_order(current, form_inputs, state),
        "waf_bypass": simulate_waf_bypass,
        "oob_exfil": simulate_oob_exfil,
        "fix_plan": simulate_fix_plan,
    }

    evaluator = evaluators.get(simulation_type)
    if evaluator is None:
        result = build_result(
            False,
            "Unsupported simulation profile",
            ["[sim] No evaluator found for this challenge."],
            "The configured challenge type is missing an evaluator.",
        )
    else:
        result = evaluator(challenge, inputs)

    if result["solved"] and not result.get("flag"):
        result["flag"] = challenge["flag"]
    if result["solved"] and result.get("flag") and not result.get("state_message"):
        result["state_message"] = "Challenge completed. Correct flag captured from the mock database."
    return result


def simulate_login_flow(challenge: dict, inputs: dict[str, str]) -> dict:
    username_raw = inputs.get("username", "")
    password_raw = inputs.get("password", "")
    config = challenge["simulation"]
    expected_flag = get_expected_flag(challenge)
    blocked, processed_inputs, filter_trace = prepare_login_inputs(username_raw, password_raw, config["filter_variant"])
    terminal = [
        "[login] Executing login sandbox.",
        f"[login] filter={config['filter_variant']}",
    ]

    if blocked:
        return build_result(
            False,
            "Input blocked",
            terminal + ["[login] Filter rejected the username payload."],
            "The current filter variant blocked the payload before the unsafe query template was reached.",
            filter_trace=filter_trace,
            display_message="Payload bị chặn bởi filter hiện tại.",
        )

    exact_user = find_user_by_username(processed_inputs["username"].strip())
    if exact_user and exact_user["password"] == processed_inputs["password"]:
        solved = exact_user["username"] == "admin"
        captured_flag = str(exact_user.get("flag") or "") if solved else None
        return build_result(
            solved,
            "Login success",
            terminal + [f"[login] Exact credential match for {exact_user['username']}."],
            challenge["success_explanation"],
            mock_rows=[{key: exact_user[key] for key in ("id", "username", "role")}],
            filter_trace=filter_trace,
            display_message=f"Đăng nhập thành công với username là {exact_user['username']}, password là {processed_inputs['password']}.",
            flag=captured_flag,
        )

    if exact_user:
        return build_result(
            False,
            "Wrong password",
            terminal + [f"[login] Username matched {exact_user['username']} but password was incorrect."],
            "The username exists in the mock dataset, but the password check failed.",
            filter_trace=filter_trace,
            display_message="Sai mật khẩu.",
        )

    try:
        rendered_query = render_query_template(challenge.get("unsafe_query", ""), processed_inputs)
        rendered_query = normalize_login_query(rendered_query)
        executed = execute_sql_sandbox(rendered_query, datasets=get_sandbox_datasets())
    except (SandboxSqlError, SandboxRuntimeError) as error:
        return build_result(
            False,
            "Login query failed",
            terminal + build_db_error_lines(error),
            "The rendered login query is not valid SQL in the sandbox.",
            filter_trace=filter_trace,
            display_message="Câu query đăng nhập không hợp lệ.",
        )

    rows = executed["rows"]
    if rows:
        session_user = pick_first_row(rows) or {}
        session_username = str(session_user.get("username", "unknown"))
        admin_row = next(
            (
                row
                for row in rows
                if str(row.get("username", "")).lower() == "admin" or str(row.get("role", "")).lower() == "admin"
            ),
            None,
        )
        solved = admin_row is not None
        return build_result(
            solved,
            "Login bypass",
            terminal + [f"[login] SQL sandbox returned {len(rows)} row(s)."],
            challenge["success_explanation"],
            mock_rows=rows,
            filter_trace=filter_trace,
            display_message=f"Login bypass thành công. Query trả về {len(rows)} user và hệ thống chọn {session_username}.",
            flag=expected_flag if solved else None,
        )

    return build_result(
        False,
        "Login failed",
        terminal + ["[login] SQL sandbox returned no row."],
        "The rendered query executed but did not return any matching user.",
        filter_trace=filter_trace,
        display_message="Sai mật khẩu.",
    )


def simulate_product_union(challenge: dict, inputs: dict[str, str]) -> dict:
    payload_raw = inputs.get("payload", "")
    config = challenge["simulation"]
    expected_flag = get_expected_flag(challenge)
    blocked, filter_trace = apply_filter_variant(payload_raw, config["filter_variant"])
    terminal = [
        "[product] Executing product sandbox.",
        f"[product] goal={config['goal']}",
        f"[product] filter={config['filter_variant']}",
    ]

    if blocked:
        return build_result(
            False,
            "Input blocked",
            terminal + ["[product] Filter rejected the payload."],
            "The active filter variant blocked this payload before the SQL execution path.",
            filter_trace=filter_trace,
            display_message="Payload bị chặn bởi filter hiện tại.",
        )

    try:
        _, executed = run_query_template(challenge, inputs)
    except (SandboxSqlError, SandboxRuntimeError) as error:
        return build_result(
            False,
            "Product query failed",
            terminal + build_db_error_lines(error),
            "The rendered product query is not valid SQL in the sandbox.",
            filter_trace=filter_trace,
            display_message="Câu query không hợp lệ.",
        )

    rows = executed["rows"]
    if not rows:
        return build_result(
            False,
            "No product found",
            terminal + ["[product] SQL sandbox returned no row."],
            "The rendered query did not return any rows.",
            filter_trace=filter_trace,
            display_message="Không tìm thấy sản phẩm.",
        )

    target_tables = sorted(table for table in executed["tables_used"] if table != "products")
    union_used = executed["union_used"]
    solved = union_used and "flags" in executed["tables_used"] and rows_contain_flag(rows, expected_flag)

    if union_used:
        target_label = ", ".join(target_tables) if target_tables else "custom projection"
        return build_result(
            solved,
            "UNION dump executed",
            terminal + [f"[product] SQL sandbox executed UNION across: {target_label}."],
            challenge["success_explanation"],
            mock_rows=rows,
            filter_trace=filter_trace,
            display_message=(
                "Đã dump được bảng flags và lấy ra flag."
                if solved
                else f"Dữ liệu bảng {target_label} đã được hiển thị."
            ),
            flag=expected_flag if solved else None,
        )

    first_row = pick_first_row(rows) or {}
    return build_result(
        solved,
        "Product loaded",
        terminal + [f"[product] SQL sandbox returned {len(rows)} product row(s)."],
        challenge["success_explanation"],
        mock_rows=rows,
        filter_trace=filter_trace,
        display_message=f"Hiển thị sản phẩm id {first_row.get('id', '?')}.",
    )


def simulate_error_syntax(challenge: dict, inputs: dict[str, str]) -> dict:
    payload_raw = inputs.get("payload", "")
    expected_flag = get_expected_flag(challenge)
    terminal = ["[error] Evaluating parser branch.", f"[error] payload={payload_raw or '<empty>'}"]

    try:
        _, executed = run_query_template(challenge, inputs)
    except (SandboxSqlError, SandboxRuntimeError) as error:
        db_lines = build_db_error_lines(error)
        solved = lines_contain_flag(db_lines, expected_flag)
        return build_result(
            solved,
            "Error leak captured" if solved else "Syntax error leaked",
            terminal + db_lines,
            challenge["success_explanation"] if solved else "The sandbox returned an SQL error, but it did not reveal the stored flag yet.",
            display_message="Thông báo lỗi đã trả về flag." if solved else "Có lỗi SQL, nhưng chưa leak ra flag.",
            flag=expected_flag if solved else None,
        )

    rows = executed["rows"]
    if rows:
        return build_result(
            False,
            "Normal lookup",
            terminal + [f"[error] SQL sandbox returned {len(rows)} row(s) without error."],
            "The query executed normally, so this level does not count as an error leak yet.",
            mock_rows=rows,
            display_message=f"Tìm thấy {len(rows)} kết quả.",
        )

    return build_result(
        False,
        "Parser stayed quiet",
        terminal + ["[error] SQL sandbox completed without throwing an error."],
        "A valid query with no exception does not complete this error-based level.",
        display_message="Không có lỗi SQL được trả về.",
    )


def simulate_error_extract(challenge: dict, inputs: dict[str, str]) -> dict:
    config = challenge["simulation"]
    payload_raw = inputs.get("payload", "")
    expected_flag = get_expected_flag(challenge)
    terminal = ["[error] Evaluating controlled error leak.", f"[error] payload={payload_raw or '<empty>'}"]
    variables: dict[str, Any] = {}

    if config.get("leak", "").startswith("table::"):
        variables["table_name"] = config["leak"].split("::", 1)[1]

    try:
        _, executed = run_query_template(challenge, inputs, variables=variables)
    except SandboxRuntimeError as error:
        db_lines = build_db_error_lines(error)
        solved = lines_contain_flag(db_lines, expected_flag)
        return build_result(
            solved,
            "Controlled error leak simulated" if solved else "Controlled error did not reveal flag",
            terminal + db_lines,
            challenge["success_explanation"] if solved else "The error path was reached, but the message did not contain the stored category flag.",
            display_message="SQL error đã leak ra flag." if solved else "Đã có controlled error, nhưng chưa leak đúng flag.",
            flag=expected_flag if solved else None,
        )
    except SandboxSqlError as error:
        return build_result(
            False,
            "No controlled leak detected",
            terminal + build_db_error_lines(error),
            "The query failed syntactically, but it did not trigger the intended controlled error-leak path.",
            display_message="Lỗi cú pháp xảy ra, nhưng chưa leak đúng kiểu level này.",
        )

    rows = executed["rows"]
    return build_result(
        False,
        "No controlled leak detected",
        terminal + [f"[error] SQL sandbox returned {len(rows)} row(s) without an error leak."],
        "The query executed without triggering an error-based disclosure primitive.",
        mock_rows=rows,
        display_message="Không có leak error trả về.",
    )


def simulate_boolean_blind(challenge: dict, inputs: dict[str, str]) -> dict:
    config = challenge["simulation"]
    payload_raw = inputs.get("payload", "")
    expected_flag = get_expected_flag(challenge)
    terminal = ["[blind] Executing boolean branch evaluation.", f"[blind] hidden_fact={config['hidden_fact']}"]

    try:
        _, executed = run_query_template(challenge, inputs)
    except (SandboxSqlError, SandboxRuntimeError) as error:
        return build_result(
            False,
            "Boolean oracle returned FALSE",
            terminal + build_db_error_lines(error),
            "The boolean sandbox only returns TRUE for a valid query that produces at least one row.",
            boolean_result=False,
        )

    oracle_true = bool(executed["rows"])
    solved = oracle_true and "flags" in executed["tables_used"] and payload_mentions_flag(payload_raw, expected_flag)
    terminal.append(f"[blind] result={'TRUE' if oracle_true else 'FALSE'}")
    return build_result(
        solved,
        "Boolean oracle matched" if solved else ("Boolean oracle returned TRUE" if oracle_true else "Boolean oracle returned FALSE"),
        terminal,
        (
            challenge["success_explanation"]
            if solved
            else "The boolean sandbox only completes when the condition proves the real flag stored in the flags table."
        ),
        boolean_result=oracle_true,
        flag=expected_flag if solved else None,
    )


def simulate_time_blind(challenge: dict, inputs: dict[str, str]) -> dict:
    config = challenge["simulation"]
    payload_raw = inputs.get("payload", "")
    expected_flag = get_expected_flag(challenge)
    terminal = ["[time] Evaluating delayed branch.", f"[time] hidden_fact={config['hidden_fact']}"]
    signal_seen = False

    try:
        _, executed = run_query_template(challenge, inputs)
        signal_seen = executed["delay_ms"] > 0
        solved = signal_seen and "flags" in executed["tables_used"] and payload_mentions_flag(payload_raw, expected_flag)
        delay_ms = config["delay_ms"] if signal_seen else 120
    except (SandboxSqlError, SandboxRuntimeError) as error:
        delay_ms = 120
        solved = False
        terminal.extend(build_db_error_lines(error))

    time.sleep(min(delay_ms / 1000, 2.0))
    terminal.append(f"[time] simulated_delay_ms={delay_ms}")

    return build_result(
        solved,
        "Timed condition matched" if solved else ("Timing signal observed" if signal_seen else "No timing signal observed"),
        terminal,
        (
            challenge["success_explanation"]
            if solved
            else "The timer only completes the lab when the delayed condition proves the real flag stored in the flags table."
        ),
        delay_ms=delay_ms,
        flag=expected_flag if solved else None,
    )


def simulate_stacked_query(challenge: dict, inputs: dict[str, str]) -> dict:
    expected_flag = get_expected_flag(challenge)
    terminal = ["[stacked] Inspecting statement chain."]

    try:
        _, executed = run_query_template(challenge, inputs)
    except (SandboxSqlError, SandboxRuntimeError) as error:
        return build_result(
            False,
            "Secondary statement failed",
            terminal + build_db_error_lines(error),
            "The stacked sandbox only accepts valid multi-statement SQL.",
            display_message="Chuỗi stacked query không hợp lệ.",
        )

    statement_count = len(executed["statements"])
    terminal.append(f"[stacked] statement_count={statement_count}")
    solved = statement_count > 1 and "flags" in executed["tables_used"] and rows_contain_flag(executed["rows"], expected_flag)

    if statement_count > 1:
        return build_result(
            solved,
            "Stacked statement simulated" if solved else "Secondary statement executed",
            terminal + ["[stacked] Secondary statement recognized."],
            challenge["success_explanation"] if solved else "The multi-statement chain executed, but it did not retrieve the stored flag from the flags table.",
            mock_rows=executed["rows"],
            query_log=executed["query_log"],
            display_message=(
                "Stacked query đã được thực thi và lấy ra flag."
                if solved
                else "Stacked query đã được thực thi trong sandbox."
            ),
            flag=expected_flag if solved else None,
        )

    if executed["rows"]:
        return build_result(
            False,
            "Single statement executed",
            terminal + ["[stacked] Only the base SELECT executed."],
            "The sandbox executed a normal single statement only.",
            mock_rows=executed["rows"],
            query_log=executed["query_log"],
            display_message="Query thường được thực thi, chưa có stacked statement.",
        )

    return build_result(
        False,
        "Secondary statement missing",
        terminal + ["[stacked] Only one empty statement executed."],
        "Use a valid statement separator and a second valid SQL statement.",
        query_log=executed["query_log"],
        display_message="Chưa có statement thứ hai được thực thi.",
    )


def simulate_second_order(challenge: dict, inputs: dict[str, str], state: dict[str, Any]) -> dict:
    stored_value = inputs.get("stored_value", "").strip()
    trigger_action = normalize(inputs.get("trigger_action", ""))
    config = challenge["simulation"]
    expected_flag = get_expected_flag(challenge)
    terminal = [
        "[second-order] Reviewing stored input path.",
        f"[second-order] expected_trigger={config['trigger']}",
    ]

    if stored_value:
        state["stored_value"] = stored_value
        terminal.append(f"[second-order] Stored {config['state_label']} for later reuse.")

    if not state.get("stored_value"):
        return build_result(
            False,
            "Stored input required",
            terminal + ["[second-order] No stored payload present yet."],
            "Store a payload-like value first, then trigger the downstream workflow.",
            status="info",
            state_message="Chưa có payload nào được lưu cho challenge này.",
        )

    has_trigger = trigger_action == config["trigger"]
    terminal.extend(
        [
            f"[second-order] stored_value={state['stored_value']}",
            f"[second-order] trigger_received={trigger_action or '<none>'}",
        ]
    )

    if not has_trigger:
        return build_result(
            False,
            "Stored payload is ready",
            terminal + ["[second-order] Waiting for the downstream trigger."],
            "The stored value is ready. Trigger the downstream workflow to replay it inside the later query.",
            status="info",
            state_message=f"Đã lưu {config['state_label']}. Hãy trigger {config['trigger']} tiếp theo.",
        )

    query_tail = get_query_tail(challenge.get("unsafe_query", ""))
    try:
        _, executed = run_query_template(
            challenge,
            {"stored_value": state["stored_value"]},
            query_override=query_tail,
        )
        solved = (
            any(table in executed["tables_used"] for table in {"admin_notes", "hidden_messages"})
            and rows_contain_flag(executed["rows"], expected_flag)
            and (executed["union_used"] or len(executed["statements"]) > 1 or len(executed["rows"]) > 1)
        )
        return build_result(
            solved,
            "Delayed injection path simulated" if solved else "Stored value replayed safely",
            terminal + [f"[second-order] SQL sandbox replayed the stored {config['state_label']} value."],
            challenge["success_explanation"] if solved else "The stored value was replayed, but it did not broaden the downstream query result.",
            mock_rows=executed["rows"],
            query_log=executed["query_log"],
            state_message=f"{config['state_label']} đã được phát lại bên trong query phía sau.",
            display_message="Giá trị lưu trước đã được tái sử dụng trong query sau.",
            flag=expected_flag if solved else None,
        )
    except (SandboxSqlError, SandboxRuntimeError) as error:
        db_lines = build_db_error_lines(error)
        solved = lines_contain_flag(db_lines, expected_flag)
        return build_result(
            solved,
            "Delayed injection path simulated" if solved else "Delayed query failed",
            terminal + db_lines,
            challenge["success_explanation"] if solved else "The stored value reached the later query, but it still did not expose the stored second-order flag.",
            state_message=f"{config['state_label']} đã được phát lại bên trong query phía sau.",
            display_message="Giá trị lưu trước gây lỗi khi query sau tái sử dụng nó.",
            flag=expected_flag if solved else None,
        )


def simulate_waf_bypass(challenge: dict, inputs: dict[str, str]) -> dict:
    payload_raw = inputs.get("payload", "")
    variant = challenge["simulation"]["variant"]
    expected_flag = get_expected_flag(challenge)
    blocked, filter_trace = apply_filter_variant(payload_raw, variant)
    terminal = [
        "[waf] Applying safe SQL-like filter sandbox.",
        f"[waf] variant={variant}",
        f"[waf] blocked={'yes' if blocked else 'no'}",
    ]

    if blocked:
        return build_result(
            False,
            "Input blocked",
            terminal + ["[waf] Filter rejected the payload."],
            "The current filter blocked the payload before SQL execution.",
            filter_trace=filter_trace,
            display_message="Payload bị chặn bởi filter hiện tại.",
        )

    try:
        _, executed = run_query_template(challenge, inputs)
    except (SandboxSqlError, SandboxRuntimeError) as error:
        return build_result(
            False,
            "Bypass query failed",
            terminal + build_db_error_lines(error),
            "The payload passed the filter but did not form a valid SQL query in the sandbox.",
            filter_trace=filter_trace,
            display_message="Payload qua filter nhưng query không hợp lệ.",
        )

    solved = (
        (executed["union_used"] or len(executed["statements"]) > 1)
        and "flags" in executed["tables_used"]
        and rows_contain_flag(executed["rows"], expected_flag)
    )
    if solved:
        filter_trace.append("Bypass result: semantic SQL preserved, literal rule missed the payload.")
        return build_result(
            True,
            "Naive filter bypassed",
            terminal + ["[waf] Blacklist bypass demonstrated by the SQL sandbox."],
            challenge["success_explanation"],
            mock_rows=executed["rows"],
            query_log=executed["query_log"],
            filter_trace=filter_trace,
            display_message="Bypass thành công qua filter hiện tại.",
            flag=expected_flag,
        )

    if executed["rows"]:
        return build_result(
            False,
            "Normal lookup",
            terminal + ["[waf] Query executed but stayed in the normal path."],
            "The payload passed the filter, but it only executed as a normal query and did not expand the SQL semantics.",
            mock_rows=executed["rows"],
            query_log=executed["query_log"],
            filter_trace=filter_trace,
            display_message="Query thường được thực thi, chưa bypass được filter.",
        )

    filter_trace.append("Bypass result: payload still matched or failed to preserve the blocked meaning.")
    return build_result(
        False,
        "Blacklist bypass not demonstrated",
        terminal + ["[waf] Filter still blocked or payload lost meaning."],
        "This lab expects a valid query that both passes the filter and changes the SQL semantics.",
        filter_trace=filter_trace,
        display_message="Payload chưa vượt qua được filter hiện tại.",
    )


def simulate_oob_exfil(challenge: dict, inputs: dict[str, str]) -> dict:
    payload_raw = inputs.get("payload", "")
    config = challenge["simulation"]
    expected_flag = get_expected_flag(challenge)
    blocked, filter_trace = apply_filter_variant(payload_raw, config["filter_variant"])
    terminal = [
        "[oob] Executing safe out-of-band sandbox.",
        f"[oob] channel={config['channel']}",
        f"[oob] filter={config['filter_variant']}",
    ]

    if blocked:
        return build_result(
            False,
            "Input blocked",
            terminal + ["[oob] Filter rejected the payload before callback evaluation."],
            "The active filter blocked the payload before the simulated OOB primitive was reached.",
            filter_trace=filter_trace,
            display_message="Payload bị chặn bởi filter hiện tại.",
        )

    try:
        _, executed = run_query_template(challenge, inputs)
    except (SandboxSqlError, SandboxRuntimeError) as error:
        return build_result(
            False,
            "OOB query failed",
            terminal + build_db_error_lines(error),
            "The rendered query did not execute cleanly in the sandbox, so no callback was recorded.",
            filter_trace=filter_trace,
            display_message="Query không hợp lệ, callback OOB chưa được ghi nhận.",
        )

    oob_events = executed.get("oob_events", [])
    matching_events = [
        event
        for event in oob_events
        if event.get("channel") == config["channel"] and expected_flag and expected_flag in str(event.get("target", ""))
    ]
    solved = bool(matching_events)

    if solved:
        event = matching_events[0]
        return build_result(
            True,
            "Out-of-band callback captured",
            terminal + [f"[oob] Captured {event['channel']} callback -> {event['target']}"],
            challenge["success_explanation"],
            query_log=executed["query_log"],
            filter_trace=filter_trace,
            display_message=f"Đã ghi nhận callback {event['channel']} nhưng chưa đúng flag.",
            flag=expected_flag,
        )

    if oob_events:
        event = oob_events[0]
        return build_result(
            False,
            "Wrong callback target",
            terminal + [f"[oob] Observed {event['channel']} callback -> {event['target']}"],
            "A simulated callback was observed, but it did not contain the correct stored flag for this category.",
            query_log=executed["query_log"],
            filter_trace=filter_trace,
            display_message="Đã có callback OOB, nhưng chưa exfil đúng flag.",
        )

    return build_result(
        False,
        "No callback observed",
        terminal + ["[oob] Query executed without any outbound callback primitive."],
        "The query ran in the sandbox, but it did not trigger a simulated DNS or HTTP callback.",
        query_log=executed["query_log"],
        filter_trace=filter_trace,
        display_message="Chưa có callback OOB nào được ghi nhận.",
    )


def simulate_fix_plan(challenge: dict, inputs: dict[str, str]) -> dict:
    fix_text = normalize(inputs.get("fix", ""))
    config = challenge["simulation"]
    required_keywords = config["required_keywords"]
    alternative_keywords = config.get("alternatives", [])

    matched_required = sum(1 for keyword in required_keywords if keyword in fix_text)
    matched_alternatives = sum(1 for keyword in alternative_keywords if keyword in fix_text)
    solved = matched_required == len(required_keywords) or (matched_required + matched_alternatives) >= len(required_keywords)

    terminal = [
        "[defense] Evaluating secure coding response.",
        f"[defense] matched_required={matched_required}/{len(required_keywords)}",
        f"[defense] matched_alternatives={matched_alternatives}",
    ]

    if solved:
        return build_result(
            True,
            "Secure fix accepted",
            terminal + ["[defense] Secure controls accepted."],
            challenge["success_explanation"],
        )

    return build_result(
        False,
        "Fix plan incomplete",
        terminal + ["[defense] Missing one or more required controls."],
        "Include the secure coding controls required by the hint for this level.",
    )
