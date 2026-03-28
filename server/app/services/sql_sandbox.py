from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ..data.mock_data import MOCK_DATASETS


class SandboxSqlError(Exception):
    pass


class SandboxRuntimeError(Exception):
    def __init__(self, message: str, *, code: str = "1105", sqlstate: str = "HY000"):
        super().__init__(message)
        self.code = code
        self.sqlstate = sqlstate


@dataclass
class Token:
    kind: str
    value: Any
    raw: str


@dataclass
class Identifier:
    name: str


@dataclass
class FunctionCall:
    name: str
    args: list[Any]


@dataclass
class BinaryOp:
    left: Any
    operator: str
    right: Any


@dataclass
class UnaryOp:
    operator: str
    operand: Any


@dataclass
class CaseExpression:
    branches: list[tuple[Any, Any]]
    else_expr: Any | None


@dataclass
class Subquery:
    sql: str


@dataclass
class SelectItem:
    expr: Any
    alias: str
    raw: str


@dataclass
class TableSource:
    name: str
    alias: str | None
    args: list[Any]
    join_type: str
    on_expr: Any | None


@dataclass
class SelectStatement:
    select_items: list[SelectItem]
    table_sources: list[TableSource]
    where_expr: Any | None
    group_by: list[Any]
    having_expr: Any | None
    order_by: list[tuple[str | int, bool]]
    limit_count: int | None
    limit_offset: int
    distinct: bool
    raw: str


def get_sandbox_datasets() -> dict[str, list[dict[str, Any]]]:
    return deepcopy(MOCK_DATASETS)


def render_query_template(template: str, inputs: dict[str, str] | None) -> str:
    rendered = template or ""
    for name, value in (inputs or {}).items():
        rendered = rendered.replace(f"<{name}>", value or "")
    return rendered


def normalize_mysql_backslash_quotes(sql: str) -> str:
    return (sql or "").replace("\\'", "''")


def expand_mysql_version_comments(sql: str) -> str:
    return re.sub(
        r"/\*!\d*\s*(.*?)\*/",
        lambda match: f" {match.group(1).strip()} ",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )


def reconstruct_fragmented_keywords(sql: str) -> str:
    rebuilt = sql
    keywords = [
        "select",
        "union",
        "from",
        "where",
        "order",
        "group",
        "having",
        "sleep",
        "benchmark",
        "insert",
        "update",
        "delete",
        "and",
        "or",
    ]

    changed = True
    while changed:
        changed = False
        for keyword in keywords:
            for split_index in range(1, len(keyword)):
                pattern = re.compile(
                    rf"(?i){re.escape(keyword[:split_index])}\s*/\*.*?\*/\s*{re.escape(keyword[split_index:])}",
                    flags=re.DOTALL,
                )
                rebuilt, replacements = pattern.subn(keyword.upper(), rebuilt)
                changed = changed or replacements > 0

    return rebuilt


def strip_sql_comments(sql: str) -> str:
    result: list[str] = []
    index = 0
    in_string = False

    while index < len(sql):
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < len(sql) else ""

        if char == "'":
            result.append(char)
            if in_string and nxt == "'":
                result.append(nxt)
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue

        if not in_string and char == "-" and nxt == "-":
            index += 2
            while index < len(sql) and sql[index] not in "\r\n":
                index += 1
            result.append(" ")
            continue

        if not in_string and char == "#":
            index += 1
            while index < len(sql) and sql[index] not in "\r\n":
                index += 1
            result.append(" ")
            continue

        if not in_string and char == "/" and nxt == "*":
            index += 2
            while index + 1 < len(sql) and not (sql[index] == "*" and sql[index + 1] == "/"):
                index += 1
            index += 2
            result.append(" ")
            continue

        result.append(char)
        index += 1

    return "".join(result)


def has_balanced_quotes(sql: str) -> bool:
    in_string = False
    index = 0

    while index < len(sql):
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < len(sql) else ""
        if char == "'":
            if in_string and nxt == "'":
                index += 2
                continue
            in_string = not in_string
        index += 1

    return not in_string


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    index = 0
    depth = 0
    in_string = False
    delimiter_length = len(delimiter)
    upper_text = text.upper()
    upper_delimiter = delimiter.upper()
    needs_boundaries = any(character.isalnum() or character == "_" for character in delimiter)

    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""

        if char == "'":
            current.append(char)
            if in_string and nxt == "'":
                current.append(nxt)
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue

        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)

            if depth == 0 and upper_text[index : index + delimiter_length] == upper_delimiter:
                if needs_boundaries:
                    before = upper_text[index - 1] if index > 0 else " "
                    after = upper_text[index + delimiter_length] if index + delimiter_length < len(text) else " "
                    if (before.isalnum() or before == "_") or (after.isalnum() or after == "_"):
                        current.append(char)
                        index += 1
                        continue

                parts.append("".join(current).strip())
                current = []
                index += delimiter_length
                continue

        current.append(char)
        index += 1

    parts.append("".join(current).strip())
    return [part for part in parts if part]


def find_top_level_keyword(text: str, keyword: str) -> int:
    upper_text = text.upper()
    upper_keyword = keyword.upper()
    index = 0
    depth = 0
    in_string = False
    keyword_length = len(keyword)
    needs_boundaries = keyword.strip() == keyword and any(character.isalnum() or character == "_" for character in keyword)

    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""

        if char == "'":
            if in_string and nxt == "'":
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue

        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)

            if depth == 0 and upper_text[index : index + keyword_length] == upper_keyword:
                if needs_boundaries:
                    before = upper_text[index - 1] if index > 0 else " "
                    after = upper_text[index + keyword_length] if index + keyword_length < len(text) else " "
                    if (before.isalnum() or before == "_") or (after.isalnum() or after == "_"):
                        index += 1
                        continue
                return index

        index += 1

    return -1


def find_top_level_clause(text: str, clause: str) -> int:
    upper_text = text.upper()
    upper_clause = clause.upper()
    index = 0
    depth = 0
    in_string = False
    clause_length = len(clause)

    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""

        if char == "'":
            if in_string and nxt == "'":
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue

        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)

            if depth == 0 and upper_text[index : index + clause_length] == upper_clause:
                before = upper_text[index - 1] if index > 0 else " "
                after = upper_text[index + clause_length] if index + clause_length < len(text) else " "
                if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                    return index

        index += 1

    return -1


def split_compound_select(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    index = 0
    depth = 0
    in_string = False
    upper_text = text.upper()

    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""

        if char == "'":
            current.append(char)
            if in_string and nxt == "'":
                current.append(nxt)
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue

        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)

            if depth == 0 and upper_text[index : index + 10] == "UNION ALL ":
                parts.append("".join(current).strip())
                current = []
                index += 10
                continue

            if depth == 0 and upper_text[index : index + 6] == "UNION ":
                parts.append("".join(current).strip())
                current = []
                index += 6
                continue

        current.append(char)
        index += 1

    parts.append("".join(current).strip())
    return [part for part in parts if part]


def tokenize_expression(expression: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0

    while index < len(expression):
        char = expression[index]

        if char.isspace():
            index += 1
            continue

        if expression[index : index + 2] in {"<=", ">=", "<>", "!=", "||"}:
            raw = expression[index : index + 2]
            tokens.append(Token("OP", raw.upper(), raw))
            index += 2
            continue

        if expression[index : index + 2].lower() == "0x":
            end = index + 2
            while end < len(expression) and expression[end] in "0123456789abcdefABCDEF":
                end += 1
            raw = expression[index:end]
            hex_value = raw[2:]
            try:
                value = bytes.fromhex(hex_value).decode("utf-8")
                tokens.append(Token("STRING", value, raw))
            except Exception:
                tokens.append(Token("NUMBER", int(hex_value or "0", 16), raw))
            index = end
            continue

        if char in "=<>+-/*":
            tokens.append(Token("OP", char, char))
            index += 1
            continue

        if char in "(),*":
            tokens.append(Token(char, char, char))
            index += 1
            continue

        if char == "'":
            end = index + 1
            value_parts: list[str] = []
            while end < len(expression):
                current = expression[end]
                nxt = expression[end + 1] if end + 1 < len(expression) else ""
                if current == "'" and nxt == "'":
                    value_parts.append("'")
                    end += 2
                    continue
                if current == "'":
                    break
                value_parts.append(current)
                end += 1
            if end >= len(expression) or expression[end] != "'":
                raise SandboxSqlError("Unterminated string literal")
            raw = expression[index : end + 1]
            tokens.append(Token("STRING", "".join(value_parts), raw))
            index = end + 1
            continue

        if char in {"x", "X"} and nxt == "'":
            end = index + 2
            value_parts: list[str] = []
            while end < len(expression) and expression[end] != "'":
                value_parts.append(expression[end])
                end += 1
            if end >= len(expression):
                raise SandboxSqlError("Unterminated hex literal")
            raw = expression[index : end + 1]
            try:
                value = bytes.fromhex("".join(value_parts)).decode("utf-8")
            except Exception:
                value = raw
            tokens.append(Token("STRING", value, raw))
            index = end + 1
            continue

        if char.isdigit():
            end = index + 1
            while end < len(expression) and (expression[end].isdigit() or expression[end] == "."):
                end += 1
            raw = expression[index:end]
            value = float(raw) if "." in raw else int(raw)
            tokens.append(Token("NUMBER", value, raw))
            index = end
            continue

        if expression[index : index + 9].lower() == "@@version":
            tokens.append(Token("IDENT", "@@version", "@@version"))
            index += 9
            continue

        if char.isalpha() or char in {"_", "@", "$"}:
            end = index + 1
            while end < len(expression) and (expression[end].isalnum() or expression[end] in {"_", "@", ".", "$"}):
                end += 1
            raw = expression[index:end]
            upper = raw.upper()
            if upper in {
                "AND",
                "OR",
                "NOT",
                "LIKE",
                "GLOB",
                "REGEXP",
                "MATCH",
                "BETWEEN",
                "EXISTS",
                "NULL",
                "SELECT",
                "FROM",
                "WHERE",
                "ORDER",
                "BY",
                "LIMIT",
                "OFFSET",
                "CASE",
                "WHEN",
                "THEN",
                "ELSE",
                "END",
                "AS",
                "IS",
                "IN",
                "DISTINCT",
                "ASC",
                "DESC",
            }:
                tokens.append(Token(upper, upper, raw))
            else:
                tokens.append(Token("IDENT", raw, raw))
            index = end
            continue

        raise SandboxSqlError(f"Unexpected token near {expression[index:index + 10]!r}")

    return tokens


class ExpressionParser:
    def __init__(self, expression: str):
        self.tokens = tokenize_expression(expression)
        self.index = 0

    def current(self) -> Token | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def match(self, *kinds: str) -> Token | None:
        token = self.current()
        if token and token.kind in kinds:
            self.index += 1
            return token
        return None

    def expect(self, kind: str) -> Token:
        token = self.match(kind)
        if token is None:
            raise SandboxSqlError(f"Expected {kind}")
        return token

    def parse(self) -> Any:
        node = self.parse_or()
        if self.current() is not None:
            raise SandboxSqlError(f"Unexpected token {self.current().raw!r}")
        return node

    def parse_or(self) -> Any:
        node = self.parse_and()
        while self.match("OR"):
            node = BinaryOp(node, "OR", self.parse_and())
        return node

    def parse_and(self) -> Any:
        node = self.parse_not()
        while self.match("AND"):
            node = BinaryOp(node, "AND", self.parse_not())
        return node

    def parse_not(self) -> Any:
        if self.match("NOT"):
            return UnaryOp("NOT", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Any:
        left = self.parse_concat()
        token = self.current()
        if token and token.kind == "NOT":
            self.index += 1
            token = self.current()
            if token and token.kind == "IN":
                self.index += 1
                self.expect("(")
                values = []
                if self.match(")"):
                    return BinaryOp(left, "NOT IN", values)
                while True:
                    values.append(self.parse_or())
                    if self.match(")"):
                        break
                    self.expect(",")
                return BinaryOp(left, "NOT IN", values)
            if token and token.kind in {"LIKE", "GLOB", "REGEXP", "MATCH"}:
                self.index += 1
                right = self.parse_concat()
                return BinaryOp(left, f"NOT {token.value}", right)
            if token and token.kind == "BETWEEN":
                self.index += 1
                lower_bound = self.parse_concat()
                self.expect("AND")
                upper_bound = self.parse_concat()
                return FunctionCall("not_between", [left, lower_bound, upper_bound])
            raise SandboxSqlError("Unsupported NOT expression")
        if token and token.kind == "IN":
            self.index += 1
            self.expect("(")
            values = []
            if self.match(")"):
                return BinaryOp(left, "IN", values)
            while True:
                values.append(self.parse_or())
                if self.match(")"):
                    break
                self.expect(",")
            return BinaryOp(left, "IN", values)
        if token and token.kind == "BETWEEN":
            self.index += 1
            lower_bound = self.parse_concat()
            self.expect("AND")
            upper_bound = self.parse_concat()
            return FunctionCall("between", [left, lower_bound, upper_bound])
        if token and token.kind == "IS":
            self.index += 1
            is_not = self.match("NOT")
            right = self.parse_concat()
            return BinaryOp(left, "IS NOT" if is_not else "IS", right)
        if token and token.kind in {"OP", "LIKE", "GLOB", "REGEXP", "MATCH"}:
            self.index += 1
            right = self.parse_concat()
            return BinaryOp(left, token.value, right)
        return left

    def parse_concat(self) -> Any:
        node = self.parse_additive()
        while self.current() and self.current().kind == "OP" and self.current().value == "||":
            self.index += 1
            node = BinaryOp(node, "||", self.parse_additive())
        return node

    def parse_additive(self) -> Any:
        node = self.parse_term()
        while self.current() and self.current().kind == "OP" and self.current().value in {"+", "-"}:
            operator = self.current().value
            self.index += 1
            node = BinaryOp(node, operator, self.parse_term())
        return node

    def parse_term(self) -> Any:
        node = self.parse_unary()
        while self.current() and self.current().kind == "OP" and self.current().value in {"*", "/"}:
            operator = self.current().value
            self.index += 1
            node = BinaryOp(node, operator, self.parse_unary())
        return node

    def parse_unary(self) -> Any:
        token = self.current()
        if token and token.kind == "OP" and token.value in {"+", "-"}:
            self.index += 1
            return UnaryOp(token.value, self.parse_unary())
        return self.parse_primary()

    def parse_case(self) -> Any:
        self.expect("CASE")
        branches: list[tuple[Any, Any]] = []
        else_expr = None

        while self.match("WHEN"):
            condition = self.parse_or()
            self.expect("THEN")
            result = self.parse_or()
            branches.append((condition, result))

        if self.match("ELSE"):
            else_expr = self.parse_or()

        self.expect("END")
        return CaseExpression(branches, else_expr)

    def parse_primary(self) -> Any:
        token = self.current()
        if token is None:
            raise SandboxSqlError("Unexpected end of expression")

        if token.kind == "NUMBER":
            self.index += 1
            return token.value

        if token.kind == "STRING":
            self.index += 1
            return token.value

        if token.kind == "NULL":
            self.index += 1
            return None

        if token.kind == "CASE":
            return self.parse_case()

        if token.kind == "EXISTS":
            self.index += 1
            self.expect("(")
            start = self.index
            depth = 1
            while self.index < len(self.tokens):
                current = self.tokens[self.index]
                if current.kind == "(":
                    depth += 1
                elif current.kind == ")":
                    depth -= 1
                    if depth == 0:
                        sql = " ".join(
                            token.raw if isinstance(token.raw, str) else str(token.raw)
                            for token in self.tokens[start:self.index]
                        )
                        self.index += 1
                        return FunctionCall("exists", [Subquery(sql)])
                self.index += 1
            raise SandboxSqlError("Unclosed EXISTS subquery")

        if token.kind == "IDENT":
            self.index += 1
            name = token.value
            if self.match("("):
                if name.lower() == "cast":
                    expr = self.parse_or()
                    self.expect("AS")
                    type_token = self.current()
                    if type_token is None:
                        raise SandboxSqlError("CAST requires a type")
                    self.index += 1
                    self.expect(")")
                    return FunctionCall(name, [expr, str(type_token.value if type_token.value is not None else type_token.raw)])

                args: list[Any] = []
                if not self.match(")"):
                    while True:
                        if self.match("*") or (self.current() and self.current().kind == "OP" and self.current().value == "*"):
                            if self.current() and self.current().kind == "OP" and self.current().value == "*":
                                self.index += 1
                            args.append("*")
                        else:
                            args.append(self.parse_or())
                        if self.match(")"):
                            break
                        self.expect(",")
                return FunctionCall(name, args)
            return Identifier(name)

        if token.kind == "(":
            self.index += 1
            sub_tokens = self.tokens[self.index :]
            if sub_tokens and sub_tokens[0].kind == "SELECT":
                depth = 1
                start = self.index
                while self.index < len(self.tokens):
                    current = self.tokens[self.index]
                    if current.kind == "(":
                        depth += 1
                    elif current.kind == ")":
                        depth -= 1
                        if depth == 0:
                            sql = " ".join(token.raw if isinstance(token.raw, str) else str(token.raw) for token in self.tokens[start:self.index])
                            self.index += 1
                            return Subquery(sql)
                    self.index += 1
                raise SandboxSqlError("Unclosed subquery")

            node = self.parse_or()
            self.expect(")")
            return node

        if token.kind == "SELECT":
            self.index += 1
            return Identifier("select")

        raise SandboxSqlError(f"Unexpected token {token.raw!r}")


def parse_expression(expression: str) -> Any:
    return ExpressionParser(expression).parse()


def split_alias(item_text: str, index: int) -> tuple[str, str]:
    match = re.match(r"(?is)(.+?)\s+as\s+([a-z_][\w]*)\s*$", item_text.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()

    compact = item_text.strip()
    if re.fullmatch(r"[a-z_][\w.]*", compact, flags=re.IGNORECASE):
        return compact, compact.split(".")[-1]

    return compact, f"column{index}"


def parse_select_items(text: str) -> list[SelectItem]:
    items: list[SelectItem] = []
    for index, raw_item in enumerate(split_top_level(text, ","), start=1):
        if raw_item.strip() == "*":
            items.append(SelectItem("*", "*", "*"))
            continue
        expr_text, alias = split_alias(raw_item, index)
        items.append(SelectItem(parse_expression(expr_text), alias, raw_item.strip()))
    return items


def parse_order_specs(order_text: str | None) -> list[tuple[str | int, bool]]:
    if not order_text:
        return []

    specs: list[tuple[str | int, bool]] = []
    for raw_part in split_top_level(order_text, ","):
        compact = collapse_whitespace(raw_part)
        if not compact:
            continue
        tokens = compact.split(" ")
        descending = False
        if len(tokens) > 1 and tokens[-1].upper() in {"ASC", "DESC"}:
            descending = tokens[-1].upper() == "DESC"
            target = " ".join(tokens[:-1]).strip()
        else:
            target = compact

        if re.fullmatch(r"\d+", target):
            specs.append((int(target), descending))
        else:
            specs.append((target.lower(), descending))
    return specs


def infer_projection_columns(statement: SelectStatement, row_contexts: list[dict[str, Any] | None], runtime: dict[str, Any]) -> list[str]:
    projection_columns: list[str] = []

    if any(item.expr == "*" for item in statement.select_items):
        sample_context = next((context for context in row_contexts if context is not None), None)
        if sample_context:
            for key in sample_context.keys():
                if "." in key:
                    continue
                lowered = key.lower()
                if lowered not in projection_columns:
                    projection_columns.append(lowered)
        else:
            for source in statement.table_sources:
                _, source_columns = materialize_source_rows(source, runtime)
                for column in source_columns:
                    lowered = column.lower()
                    if lowered not in projection_columns:
                        projection_columns.append(lowered)

    for item in statement.select_items:
        if item.expr == "*":
            continue
        alias = item.alias.lower()
        if alias not in projection_columns:
            projection_columns.append(alias)

    return projection_columns


def infer_projection_width(statement: SelectStatement, runtime: dict[str, Any]) -> int:
    if all(item.expr != "*" for item in statement.select_items):
        return len(statement.select_items)
    row_contexts = build_join_contexts(statement, runtime)
    return len(infer_projection_columns(statement, row_contexts, runtime))


def parse_table_reference(source_text: str, join_type: str, on_text: str | None) -> TableSource:
    source = collapse_whitespace(source_text)
    function_match = re.match(r"(?is)^([a-z_][\w.]*)\((.*?)\)(?:\s+(?:as\s+)?([a-z_][\w]*))?$", source)
    if function_match:
        args_text = function_match.group(2).strip()
        args = [parse_expression(part) for part in split_top_level(args_text, ",")] if args_text else []
        return TableSource(
            name=function_match.group(1).lower(),
            alias=function_match.group(3).lower() if function_match.group(3) else None,
            args=args,
            join_type=join_type,
            on_expr=parse_expression(on_text) if on_text else None,
        )

    match = re.match(r"(?is)^([a-z_][\w.]*)(?:\s+(?:as\s+)?([a-z_][\w]*))?$", source)
    if not match:
        raise SandboxSqlError(f"Unsupported table source: {source_text}")
    return TableSource(
        name=match.group(1).lower(),
        alias=match.group(2).lower() if match.group(2) else None,
        args=[],
        join_type=join_type,
        on_expr=parse_expression(on_text) if on_text else None,
    )


def find_next_join_clause(text: str) -> tuple[int, str, int] | None:
    join_tokens = [
        (" LEFT JOIN ", "left", len(" LEFT JOIN ")),
        (" INNER JOIN ", "inner", len(" INNER JOIN ")),
        (" CROSS JOIN ", "cross", len(" CROSS JOIN ")),
        (" JOIN ", "inner", len(" JOIN ")),
    ]

    upper_text = text.upper()
    index = 0
    depth = 0
    in_string = False

    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""

        if char == "'":
            if in_string and nxt == "'":
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue

        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)

            if depth == 0:
                for token, join_type, token_len in join_tokens:
                    if upper_text[index : index + token_len] == token:
                        return index, join_type, token_len

        index += 1

    return None


def parse_from_clause(from_text: str) -> list[TableSource]:
    compact = collapse_whitespace(from_text)
    if not compact:
        return []

    if find_next_join_clause(f" {compact} ") is None:
        pieces = split_top_level(compact, ",")
        if not pieces:
            return []
        sources = [parse_table_reference(pieces[0], "base", None)]
        for piece in pieces[1:]:
            sources.append(parse_table_reference(piece, "comma", None))
        return sources

    wrapped = f" {compact} "
    first_join = find_next_join_clause(wrapped)
    if first_join is None:
        return [parse_table_reference(compact, "base", None)]

    first_join_index, _, _ = first_join
    sources = [parse_table_reference(wrapped[:first_join_index].strip(), "base", None)]
    cursor = first_join_index

    while True:
        join_info = find_next_join_clause(wrapped[cursor:])
        if join_info is None:
            break
        relative_index, join_type, token_len = join_info
        start = cursor + relative_index + token_len
        next_join = find_next_join_clause(wrapped[start:])
        end = start + next_join[0] if next_join else len(wrapped)
        segment = wrapped[start:end].strip()
        on_index = find_top_level_clause(segment, "ON")
        if on_index >= 0:
            source_segment = segment[:on_index].strip()
            on_text = segment[on_index + len("ON") :].strip()
        else:
            source_segment = segment
            on_text = None
        sources.append(parse_table_reference(source_segment, join_type, on_text))
        if next_join is None:
            break
        cursor = end

    return sources


def parse_select(statement: str) -> list[SelectStatement]:
    cleaned = collapse_whitespace(statement)
    cleaned = re.sub(r"\*(?=FROM\b)", "* ", cleaned, flags=re.IGNORECASE)
    if not cleaned.lower().startswith("select "):
        raise SandboxSqlError("Only SELECT statements are supported in this branch")

    parts = split_compound_select(cleaned)
    statements: list[SelectStatement] = []

    for part in parts:
        current = collapse_whitespace(part)
        if not current.lower().startswith("select "):
            raise SandboxSqlError("Malformed UNION branch")

        body = current[7:]
        distinct = False
        if body.upper().startswith("DISTINCT "):
            distinct = True
            body = body[9:]
        from_index = find_top_level_clause(body, "FROM")
        where_index = find_top_level_clause(body, "WHERE")
        group_index = find_top_level_clause(body, "GROUP BY")
        having_index = find_top_level_clause(body, "HAVING")
        order_index = find_top_level_clause(body, "ORDER BY")
        limit_index = find_top_level_clause(body, "LIMIT")

        limit = len(body)
        first_break = min(
            [position for position in [from_index, where_index, group_index, having_index, order_index, limit_index] if position >= 0],
            default=limit,
        )
        select_text = body[:first_break].strip()

        from_text = None
        where_text = None
        group_text = None
        having_text = None
        order_text = None
        limit_text = None

        if from_index >= 0:
            from_start = from_index + len("FROM")
            from_end = min(
                [
                    position
                    for position in [where_index, group_index, having_index, order_index, limit_index]
                    if position >= 0 and position > from_index
                ],
                default=limit,
            )
            from_text = body[from_start:from_end].strip()

        if where_index >= 0:
            where_start = where_index + len("WHERE")
            where_end = min(
                [position for position in [group_index, having_index, order_index, limit_index] if position >= 0 and position > where_index],
                default=limit,
            )
            where_text = body[where_start:where_end].strip()

        if group_index >= 0:
            group_start = group_index + len("GROUP BY")
            group_end = min(
                [position for position in [having_index, order_index, limit_index] if position >= 0 and position > group_index],
                default=limit,
            )
            group_text = body[group_start:group_end].strip()

        if having_index >= 0:
            having_start = having_index + len("HAVING")
            having_end = min(
                [position for position in [order_index, limit_index] if position >= 0 and position > having_index],
                default=limit,
            )
            having_text = body[having_start:having_end].strip()

        if order_index >= 0:
            order_start = order_index + len("ORDER BY")
            order_end = limit_index if limit_index >= 0 and limit_index > order_index else limit
            order_text = body[order_start:order_end].strip()

        if limit_index >= 0:
            limit_start = limit_index + len("LIMIT")
            limit_text = body[limit_start:].strip()

        limit_count: int | None = None
        limit_offset = 0
        if limit_text:
            normalized_limit = collapse_whitespace(limit_text)
            if "," in normalized_limit:
                offset_text, count_text = [part.strip() for part in normalized_limit.split(",", 1)]
                limit_offset = int(float(offset_text))
                limit_count = int(float(count_text))
            elif " OFFSET " in normalized_limit.upper():
                offset_index = find_top_level_keyword(normalized_limit, " OFFSET ")
                count_text = normalized_limit[:offset_index].strip()
                offset_text = normalized_limit[offset_index + len(" OFFSET ") :].strip()
                limit_count = int(float(count_text))
                limit_offset = int(float(offset_text))
            else:
                limit_count = int(float(normalized_limit))

        statements.append(
            SelectStatement(
                select_items=parse_select_items(select_text),
                table_sources=parse_from_clause(from_text or ""),
                where_expr=parse_expression(where_text) if where_text else None,
                group_by=[parse_expression(part.strip()) for part in split_top_level(group_text, ",")] if group_text else [],
                having_expr=parse_expression(having_text) if having_text else None,
                order_by=parse_order_specs(order_text),
                limit_count=limit_count,
                limit_offset=limit_offset,
                distinct=distinct,
                raw=current,
            )
        )

    return statements


def infer_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def build_create_sql(table_name: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"CREATE TABLE {table_name} ();"

    first_row = rows[0]
    columns = [f"{column} {infer_type_name(value)}" for column, value in first_row.items()]
    return f"CREATE TABLE {table_name} ({', '.join(columns)});"


def build_pragma_table_info(table_name: str, datasets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = datasets.get(table_name, [])
    if not rows:
        return []

    pragma_rows = []
    for index, (column, value) in enumerate(rows[0].items()):
        pragma_rows.append(
            {
                "cid": index,
                "name": column,
                "type": infer_type_name(value),
                "notnull": 0,
                "dflt_value": None,
                "pk": 1 if column == "id" else 0,
            }
        )
    return pragma_rows


def get_virtual_table_rows(table_name: str, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    datasets = runtime["datasets"]
    if table_name in {"sqlite_master", "sqlite_schema"}:
        return [
            {
                "type": "table",
                "name": dataset_name,
                "tbl_name": dataset_name,
                "rootpage": 0,
                "sql": build_create_sql(dataset_name, dataset_rows),
            }
            for dataset_name, dataset_rows in datasets.items()
        ]

    if table_name == "pragma_database_list":
        return [{"seq": 0, "name": "main", "file": ":memory:"}]

    if table_name == "pragma_table_list":
        return [
            {
                "schema": "main",
                "name": dataset_name,
                "type": "table",
                "ncol": len(dataset_rows[0].keys()) if dataset_rows else 0,
                "wr": 0,
                "strict": 0,
            }
            for dataset_name, dataset_rows in datasets.items()
        ]

    if table_name == "information_schema.schemata":
        return [{"schema_name": "main"}]

    if table_name == "information_schema.tables":
        return [{"table_schema": "main", "table_name": dataset_name} for dataset_name in datasets]

    if table_name == "information_schema.columns":
        rows = []
        for dataset_name, dataset_rows in datasets.items():
            if not dataset_rows:
                continue
            for column_name, value in dataset_rows[0].items():
                rows.append(
                    {
                        "table_schema": "main",
                        "table_name": dataset_name,
                        "column_name": column_name,
                        "column_type": infer_type_name(value),
                        "data_type": infer_type_name(value),
                    }
                )
        return rows

    if table_name in datasets:
        return deepcopy(datasets.get(table_name, []))

    raise SandboxRuntimeError(f"Table '{table_name}' doesn't exist", code="1146", sqlstate="42S02")


def has_aggregate_expression(node: Any) -> bool:
    if isinstance(node, FunctionCall):
        if node.name.lower() in {"count", "sum", "avg", "min", "max", "group_concat"}:
            return True
        return any(has_aggregate_expression(argument) for argument in node.args if argument != "*")
    if isinstance(node, BinaryOp):
        return has_aggregate_expression(node.left) or has_aggregate_expression(node.right)
    if isinstance(node, UnaryOp):
        return has_aggregate_expression(node.operand)
    if isinstance(node, CaseExpression):
        return any(has_aggregate_expression(condition) or has_aggregate_expression(value) for condition, value in node.branches) or (
            node.else_expr is not None and has_aggregate_expression(node.else_expr)
        )
    if isinstance(node, list):
        return any(has_aggregate_expression(item) for item in node)
    return False


def sort_rows(
    rows: list[dict[str, Any]],
    order_specs: list[tuple[str | int, bool]],
    projection_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    sorted_rows = rows
    columns = [column.lower() for column in (projection_columns or (list(sorted_rows[0].keys()) if sorted_rows else []))]
    column_lookup = {column.lower(): column for column in (list(sorted_rows[0].keys()) if sorted_rows else projection_columns or [])}
    for target, descending in reversed(order_specs):
        if isinstance(target, int):
            index = target - 1
            if not (0 <= index < len(columns)):
                raise SandboxRuntimeError(
                    f"Unknown column '{target}' in 'order clause'",
                    code="1054",
                    sqlstate="42S22",
                )
            key_name = column_lookup.get(columns[index], columns[index])
            sorted_rows = sorted(sorted_rows, key=lambda current: str(current.get(key_name, "")), reverse=descending)
        else:
            lowered_target = target.lower()
            if lowered_target not in columns:
                raise SandboxRuntimeError(
                    f"Unknown column '{target}' in 'order clause'",
                    code="1054",
                    sqlstate="42S22",
                )
            key_name = column_lookup.get(lowered_target, lowered_target)
            sorted_rows = sorted(sorted_rows, key=lambda current: str(current.get(key_name, "")), reverse=descending)
    return sorted_rows


def materialize_source_rows(source: TableSource, runtime: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    if source.name == "pragma_table_info":
        if not source.args:
            return [], []
        table_name = str(evaluate_expression(source.args[0], None, runtime) or "").lower()
        rows = build_pragma_table_info(table_name, runtime["datasets"])
        runtime["tables_used"].add("pragma_table_info")
        return rows, [item["name"] for item in rows]
    if source.name == "pragma_table_xinfo":
        if not source.args:
            return [], []
        table_name = str(evaluate_expression(source.args[0], None, runtime) or "").lower()
        rows = build_pragma_table_info(table_name, runtime["datasets"])
        runtime["tables_used"].add("pragma_table_xinfo")
        return rows, [item["name"] for item in rows]
    if source.name == "pragma_table_list":
        rows = get_virtual_table_rows("pragma_table_list", runtime)
        runtime["tables_used"].add("pragma_table_list")
        return rows, list(rows[0].keys()) if rows else []

    rows = get_virtual_table_rows(source.name, runtime)
    runtime["tables_used"].add(source.name)
    if rows:
        return rows, list(rows[0].keys())
    return rows, []


def merge_row_context(existing: dict[str, Any], source: TableSource, source_row: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    alias = (source.alias or source.name.split(".")[-1]).lower()
    table_name = source.name.split(".")[-1].lower()
    normalized = {key.lower(): value for key, value in source_row.items()}

    for key, value in normalized.items():
        if key not in merged:
            merged[key] = value
        merged[f"{alias}.{key}"] = value
        merged[f"{table_name}.{key}"] = value

    return merged


def build_join_contexts(statement: SelectStatement, runtime: dict[str, Any]) -> list[dict[str, Any] | None]:
    if not statement.table_sources:
        return [None]

    base_source = statement.table_sources[0]
    base_rows, _ = materialize_source_rows(base_source, runtime)
    contexts = [merge_row_context({}, base_source, row) for row in base_rows] or ([{}] if base_source.join_type == "base" else [])

    for source in statement.table_sources[1:]:
        source_rows, source_columns = materialize_source_rows(source, runtime)
        next_contexts: list[dict[str, Any]] = []
        alias = (source.alias or source.name.split(".")[-1]).lower()
        table_name = source.name.split(".")[-1].lower()

        for context in contexts:
            matches = []
            for source_row in source_rows:
                merged = merge_row_context(context, source, source_row)
                if source.on_expr is None or truthy(evaluate_expression(source.on_expr, merged, runtime)):
                    matches.append(merged)

            if matches:
                next_contexts.extend(matches)
                continue

            if source.join_type == "left":
                null_row = {column: None for column in source_columns}
                merged = dict(context)
                for column, value in null_row.items():
                    merged[f"{alias}.{column.lower()}"] = value
                    merged[f"{table_name}.{column.lower()}"] = value
                next_contexts.append(merged)

        contexts = next_contexts

    return contexts


def coerce_comparable(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    text = str(value)
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def sql_like(value: Any, pattern: Any) -> bool:
    source = str(value or "")
    expression = re.escape(str(pattern or ""))
    expression = expression.replace(r"\%", ".*").replace(r"\_", ".")
    return bool(re.fullmatch(expression, source, flags=re.IGNORECASE))


def sql_glob(value: Any, pattern: Any) -> bool:
    source = str(value or "")
    expression = re.escape(str(pattern or ""))
    expression = expression.replace(r"\*", ".*").replace(r"\?", ".")
    return bool(re.fullmatch(expression, source))


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    if isinstance(value, str):
        return value != "" and value.lower() != "false"
    return bool(value)


def evaluate_expression(node: Any, row: dict[str, Any] | None, runtime: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [evaluate_expression(item, row, runtime) for item in node]

    if isinstance(node, (int, float, str)) or node is None:
        return node

    if isinstance(node, Identifier):
        name = node.name.lower()
        if row and name in row:
            return row[name]
        if name in runtime["variables"]:
            return runtime["variables"][name]
        if name in {"true", "false"}:
            return name == "true"
        if row is not None:
            raise SandboxRuntimeError(f"Unknown column '{node.name}' in 'field list'", code="1054", sqlstate="42S22")
        return node.name

    if isinstance(node, UnaryOp):
        value = evaluate_expression(node.operand, row, runtime)
        if node.operator == "NOT":
            return not truthy(value)
        if node.operator == "+":
            return coerce_comparable(value) or 0
        if node.operator == "-":
            return -(coerce_comparable(value) or 0)
        raise SandboxSqlError(f"Unsupported unary operator {node.operator}")

    if isinstance(node, CaseExpression):
        for condition, branch_value in node.branches:
            if truthy(evaluate_expression(condition, row, runtime)):
                return evaluate_expression(branch_value, row, runtime)
        return evaluate_expression(node.else_expr, row, runtime) if node.else_expr is not None else None

    if isinstance(node, BinaryOp):
        if node.operator == "AND":
            left_result = truthy(evaluate_expression(node.left, row, runtime))
            right_result = truthy(evaluate_expression(node.right, row, runtime))
            return left_result and right_result
        if node.operator == "OR":
            left_result = truthy(evaluate_expression(node.left, row, runtime))
            right_result = truthy(evaluate_expression(node.right, row, runtime))
            return left_result or right_result

        left = evaluate_expression(node.left, row, runtime)
        right = evaluate_expression(node.right, row, runtime)
        if node.operator == "||":
            return f"{left or ''}{right or ''}"
        if node.operator == "+":
            return (coerce_comparable(left) or 0) + (coerce_comparable(right) or 0)
        if node.operator == "-":
            return (coerce_comparable(left) or 0) - (coerce_comparable(right) or 0)
        if node.operator == "*":
            return (coerce_comparable(left) or 0) * (coerce_comparable(right) or 0)
        if node.operator == "/":
            divisor = coerce_comparable(right) or 0
            if divisor == 0:
                raise SandboxRuntimeError("division by zero", code="1365", sqlstate="22012")
            return (coerce_comparable(left) or 0) / divisor
        left_value = coerce_comparable(left)
        right_value = coerce_comparable(right)

        if node.operator in {"=", "=="}:
            return left_value == right_value
        if node.operator in {"!=", "<>"}:
            return left_value != right_value
        if node.operator == ">":
            return left_value > right_value
        if node.operator == "<":
            return left_value < right_value
        if node.operator == ">=":
            return left_value >= right_value
        if node.operator == "<=":
            return left_value <= right_value
        if node.operator == "LIKE":
            return sql_like(left, right)
        if node.operator == "NOT LIKE":
            return not sql_like(left, right)
        if node.operator == "GLOB":
            return sql_glob(left, right)
        if node.operator == "NOT GLOB":
            return not sql_glob(left, right)
        if node.operator == "REGEXP":
            return bool(re.search(str(right or ""), str(left or "")))
        if node.operator == "NOT REGEXP":
            return not bool(re.search(str(right or ""), str(left or "")))
        if node.operator == "MATCH":
            return str(right or "").lower() in str(left or "").lower()
        if node.operator == "NOT MATCH":
            return str(right or "").lower() not in str(left or "").lower()
        if node.operator == "IS":
            return left is right or left_value == right_value
        if node.operator == "IS NOT":
            return not (left is right or left_value == right_value)
        if node.operator == "IN":
            evaluated_list = [evaluate_expression(item, row, runtime) for item in right]
            return left in evaluated_list
        if node.operator == "NOT IN":
            evaluated_list = [evaluate_expression(item, row, runtime) for item in right]
            return left not in evaluated_list
        raise SandboxSqlError(f"Unsupported operator {node.operator}")

    if isinstance(node, FunctionCall):
        name = node.name.lower()
        group_rows = runtime.get("group_rows")

        if name in {"count", "sum", "avg", "min", "max", "group_concat"}:
            aggregate_rows = group_rows if group_rows is not None else ([row] if row is not None else [])
            if name == "count":
                if node.args == ["*"]:
                    return len(aggregate_rows)
                values = [evaluate_expression(node.args[0], current_row, runtime) for current_row in aggregate_rows]
                return sum(1 for value in values if value is not None)

            values = [evaluate_expression(node.args[0], current_row, runtime) for current_row in aggregate_rows]
            values = [value for value in values if value is not None]
            if name == "sum":
                return sum(coerce_comparable(value) or 0 for value in values)
            if name == "avg":
                return (sum(coerce_comparable(value) or 0 for value in values) / len(values)) if values else 0
            if name == "min":
                return min(values) if values else None
            if name == "max":
                return max(values) if values else None
            if name == "group_concat":
                separator = str(evaluate_expression(node.args[1], row, runtime)) if len(node.args) > 1 else ","
                return separator.join(str(value) for value in values)

        if name in {"substring", "substr", "mid"}:
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            start = int(evaluate_expression(node.args[1], row, runtime) or 1) - 1
            length = int(evaluate_expression(node.args[2], row, runtime)) if len(node.args) > 2 else None
            return value[start:] if length is None else value[start : start + length]

        if name == "left":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            length = int(evaluate_expression(node.args[1], row, runtime) or 0)
            return value[:length]

        if name == "length":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            return len(value)

        if name == "char_length":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            return len(value)

        if name == "concat":
            return "".join(str(evaluate_expression(argument, row, runtime) or "") for argument in node.args)

        if name == "concat_ws":
            separator = str(evaluate_expression(node.args[0], row, runtime) or "")
            values = [str(evaluate_expression(argument, row, runtime) or "") for argument in node.args[1:]]
            return separator.join(values)

        if name == "upper":
            return str(evaluate_expression(node.args[0], row, runtime) or "").upper()

        if name == "lower":
            return str(evaluate_expression(node.args[0], row, runtime) or "").lower()

        if name in {"ltrim", "rtrim", "trim"}:
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            if name == "ltrim":
                return value.lstrip()
            if name == "rtrim":
                return value.rstrip()
            return value.strip()

        if name == "replace":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            old = str(evaluate_expression(node.args[1], row, runtime) or "")
            new = str(evaluate_expression(node.args[2], row, runtime) or "")
            return value.replace(old, new)

        if name == "instr":
            haystack = str(evaluate_expression(node.args[0], row, runtime) or "")
            needle = str(evaluate_expression(node.args[1], row, runtime) or "")
            if needle == "":
                return 1
            position = haystack.find(needle)
            return position + 1 if position >= 0 else 0

        if name == "right":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            length = int(evaluate_expression(node.args[1], row, runtime) or 0)
            return value[-length:] if length else ""

        if name == "abs":
            return abs(float(evaluate_expression(node.args[0], row, runtime) or 0))

        if name in {"ceil", "ceiling"}:
            value = float(evaluate_expression(node.args[0], row, runtime) or 0)
            return int(value) if value == int(value) else int(value) + (1 if value > 0 else 0)

        if name == "floor":
            value = float(evaluate_expression(node.args[0], row, runtime) or 0)
            return int(value) if value >= 0 or value == int(value) else int(value) - 1

        if name == "round":
            value = float(evaluate_expression(node.args[0], row, runtime) or 0)
            digits = int(evaluate_expression(node.args[1], row, runtime) or 0) if len(node.args) > 1 else 0
            return round(value, digits)

        if name == "rand":
            return 0.1337

        if name == "nullif":
            left_value = evaluate_expression(node.args[0], row, runtime)
            right_value = evaluate_expression(node.args[1], row, runtime)
            return None if left_value == right_value else left_value

        if name in {"ascii", "ord", "unicode"}:
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            return ord(value[0]) if value else 0

        if name in {"char", "chr"}:
            return "".join(chr(int(evaluate_expression(argument, row, runtime) or 0)) for argument in node.args)

        if name == "hex":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            return value.encode("utf-8").hex().upper()

        if name == "unhex":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            try:
                return bytes.fromhex(value).decode("utf-8")
            except Exception as error:
                raise SandboxRuntimeError(f"Invalid hex value: {value}", code="1366", sqlstate="22018") from error

        if name == "quote":
            value = str(evaluate_expression(node.args[0], row, runtime) or "")
            return "'" + value.replace("'", "''") + "'"

        if name in {"dns_lookup", "nslookup"}:
            target = str(evaluate_expression(node.args[0], row, runtime) or "")
            runtime.setdefault("oob_events", []).append({"channel": "dns", "target": target})
            return 0

        if name in {"http_get", "http_request"}:
            target = str(evaluate_expression(node.args[0], row, runtime) or "")
            runtime.setdefault("oob_events", []).append({"channel": "http", "target": target})
            return 0

        if name == "load_file":
            target = str(evaluate_expression(node.args[0], row, runtime) or "")
            if target.startswith("\\\\"):
                runtime.setdefault("oob_events", []).append({"channel": "dns", "target": target})
            return target

        if name == "load_extension":
            target = str(evaluate_expression(node.args[0], row, runtime) or "")
            runtime.setdefault("oob_events", []).append({"channel": "http", "target": target})
            return 0

        if name in {"sleep", "pg_sleep"}:
            seconds = float(evaluate_expression(node.args[0], row, runtime) or 0)
            runtime["delay_ms"] += min(int(seconds * 1000), 2500)
            return 0

        if name == "benchmark":
            iterations = int(evaluate_expression(node.args[0], row, runtime) or 0)
            runtime["delay_ms"] += min(max(iterations // 1000, 0), 2500)
            if len(node.args) > 1:
                evaluate_expression(node.args[1], row, runtime)
            return 0

        if name == "if":
            condition = truthy(evaluate_expression(node.args[0], row, runtime))
            branch = node.args[1] if condition else node.args[2]
            return evaluate_expression(branch, row, runtime)

        if name == "iif":
            condition = truthy(evaluate_expression(node.args[0], row, runtime))
            branch = node.args[1] if condition else node.args[2]
            return evaluate_expression(branch, row, runtime)

        if name == "ifnull":
            first_value = evaluate_expression(node.args[0], row, runtime)
            return first_value if first_value is not None else evaluate_expression(node.args[1], row, runtime)

        if name == "coalesce":
            for argument in node.args:
                value = evaluate_expression(argument, row, runtime)
                if value is not None:
                    return value
            return None

        if name == "between":
            value = coerce_comparable(evaluate_expression(node.args[0], row, runtime))
            lower_bound = coerce_comparable(evaluate_expression(node.args[1], row, runtime))
            upper_bound = coerce_comparable(evaluate_expression(node.args[2], row, runtime))
            return lower_bound <= value <= upper_bound

        if name == "not_between":
            value = coerce_comparable(evaluate_expression(node.args[0], row, runtime))
            lower_bound = coerce_comparable(evaluate_expression(node.args[1], row, runtime))
            upper_bound = coerce_comparable(evaluate_expression(node.args[2], row, runtime))
            return not (lower_bound <= value <= upper_bound)

        if name == "exists":
            return truthy(evaluate_expression(node.args[0], row, runtime))

        if name == "cast":
            value = evaluate_expression(node.args[0], row, runtime)
            target_type = str(node.args[1]).lower()
            if "int" in target_type:
                try:
                    return int(str(value))
                except Exception as error:
                    raise SandboxRuntimeError(
                        f"invalid input syntax for integer: {value}",
                        code="1366",
                        sqlstate="22018",
                    ) from error
            if any(token in target_type for token in {"real", "numeric", "float", "double"}):
                try:
                    return float(str(value))
                except Exception as error:
                    raise SandboxRuntimeError(
                        f"invalid input syntax for numeric: {value}",
                        code="1366",
                        sqlstate="22018",
                    ) from error
            return str(value or "")

        if name in {"updatexml", "extractvalue"}:
            leak_value = evaluate_expression(node.args[1], row, runtime) if len(node.args) > 1 else ""
            raise SandboxRuntimeError(f"XPATH syntax error: {leak_value}", code="1105", sqlstate="HY000")

        if name == "version":
            return runtime["variables"].get("version", runtime["variables"].get("@@version", "mock-mysql-8.0.37-lab"))

        if name == "sqlite_version":
            return runtime["variables"].get("sqlite_version", "3.45.1-lab")

        if name == "sqlite_source_id":
            return runtime["variables"].get("sqlite_source_id", "2026-03-28 sandbox sqlite source id")

        if name in {"database", "schema", "current_database"}:
            return runtime["variables"].get("database", "main")

        if name in {"current_user", "user"}:
            return runtime["variables"].get("current_user", "lab_user")

        if name in {"current_date", "current_time", "current_timestamp"}:
            return runtime["variables"].get(name, "")

        raise SandboxSqlError(f"Unsupported function {node.name}")

    if isinstance(node, Subquery):
        sub_result = execute_sql_sandbox(node.sql, datasets=runtime["datasets"], variables=runtime["variables"])
        runtime["delay_ms"] = max(runtime.get("delay_ms", 0), sub_result.get("delay_ms", 0))
        runtime["tables_used"].update(sub_result.get("tables_used", set()))
        runtime["union_used"] = runtime.get("union_used", False) or sub_result.get("union_used", False)
        runtime.setdefault("oob_events", []).extend(sub_result.get("oob_events", []))
        if sub_result["rows"]:
            first_row = sub_result["rows"][0]
            return next(iter(first_row.values()))
        return 0

    raise SandboxSqlError("Unsupported expression node")


def execute_select_statement(statement: SelectStatement, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    row_contexts = build_join_contexts(statement, runtime)
    projection_columns = infer_projection_columns(statement, row_contexts, runtime)
    filtered_rows = []
    for current_row in row_contexts:
        if statement.where_expr is None or truthy(evaluate_expression(statement.where_expr, current_row, runtime)):
            filtered_rows.append(current_row)

    has_aggregate = any(has_aggregate_expression(item.expr) for item in statement.select_items)
    if statement.having_expr is not None:
        has_aggregate = has_aggregate or has_aggregate_expression(statement.having_expr)

    grouped_mode = bool(statement.group_by or statement.having_expr or has_aggregate)
    projected_rows: list[dict[str, Any]] = []

    if grouped_mode:
        groups: dict[tuple[Any, ...], list[dict[str, Any] | None]] = {}
        if statement.group_by:
            for current_row in filtered_rows:
                key = tuple(evaluate_expression(expr, current_row, runtime) for expr in statement.group_by)
                groups.setdefault(key, []).append(current_row)
        else:
            groups[("__all__",)] = filtered_rows

        if not filtered_rows and not statement.group_by:
            groups[("__all__",)] = []

        previous_group = runtime.get("group_rows")
        try:
            for group_rows in groups.values():
                sample_row = group_rows[0] if group_rows else None
                runtime["group_rows"] = group_rows
                if statement.having_expr is not None and not truthy(evaluate_expression(statement.having_expr, sample_row, runtime)):
                    continue

                if any(item.expr == "*" for item in statement.select_items) and sample_row is not None:
                    projected = {key: value for key, value in sample_row.items() if "." not in key}
                else:
                    projected = {}
                    for item in statement.select_items:
                        projected[item.alias] = evaluate_expression(item.expr, sample_row, runtime)
                projected_rows.append(projected)
        finally:
            if previous_group is None:
                runtime.pop("group_rows", None)
            else:
                runtime["group_rows"] = previous_group
    else:
        for current_row in filtered_rows:
            if any(item.expr == "*" for item in statement.select_items) and current_row is not None:
                projected_rows.append({key: value for key, value in current_row.items() if "." not in key})
                continue

            projected = {}
            for item in statement.select_items:
                projected[item.alias] = evaluate_expression(item.expr, current_row, runtime)
            projected_rows.append(projected)

    projected_rows = sort_rows(projected_rows, statement.order_by, projection_columns)

    if statement.distinct and projected_rows:
        unique_rows: list[dict[str, Any]] = []
        seen = set()
        for current in projected_rows:
            marker = tuple(sorted(current.items()))
            if marker in seen:
                continue
            seen.add(marker)
            unique_rows.append(current)
        projected_rows = unique_rows

    if statement.limit_offset:
        projected_rows = projected_rows[statement.limit_offset :]

    if statement.limit_count is not None:
        projected_rows = projected_rows[: statement.limit_count]

    return projected_rows


def parse_insert(statement: str) -> tuple[str, list[str], list[Any]]:
    match = re.match(
        r"(?is)^insert\s+into\s+([a-z_][\w.]*)\s*\((.*?)\)\s*values\s*\((.*?)\)\s*$",
        collapse_whitespace(statement),
    )
    if not match:
        raise SandboxSqlError("Unsupported INSERT syntax")
    table_name = match.group(1).lower()
    columns = [part.strip().lower() for part in split_top_level(match.group(2), ",")]
    values = [parse_expression(part.strip()) for part in split_top_level(match.group(3), ",")]
    return table_name, columns, values


def parse_update(statement: str) -> tuple[str, dict[str, Any], Any | None]:
    match = re.match(r"(?is)^update\s+([a-z_][\w.]*)\s+set\s+(.+?)(?:\s+where\s+(.+))?$", collapse_whitespace(statement))
    if not match:
        raise SandboxSqlError("Unsupported UPDATE syntax")
    table_name = match.group(1).lower()
    assignments = {}
    for part in split_top_level(match.group(2), ","):
        column, value = part.split("=", 1)
        assignments[column.strip().lower()] = parse_expression(value.strip())
    where_expr = parse_expression(match.group(3)) if match.group(3) else None
    return table_name, assignments, where_expr


def parse_delete(statement: str) -> tuple[str, Any | None]:
    match = re.match(r"(?is)^delete\s+from\s+([a-z_][\w.]*)(?:\s+where\s+(.+))?$", collapse_whitespace(statement))
    if not match:
        raise SandboxSqlError("Unsupported DELETE syntax")
    table_name = match.group(1).lower()
    where_expr = parse_expression(match.group(2)) if match.group(2) else None
    return table_name, where_expr


def parse_pragma(statement: str) -> tuple[str, str | None]:
    match = re.match(r"(?is)^pragma\s+([a-z_][\w]*)(?:\s*\(\s*'?([a-z_][\w]*)'?\s*\))?$", collapse_whitespace(statement))
    if not match:
        raise SandboxSqlError("Unsupported PRAGMA syntax")
    return match.group(1).lower(), match.group(2).lower() if match.group(2) else None


def execute_pragma(statement: str, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    pragma_name, argument = parse_pragma(statement)
    if pragma_name == "database_list":
        runtime["tables_used"].add("pragma_database_list")
        return get_virtual_table_rows("pragma_database_list", runtime)
    if pragma_name == "table_list":
        runtime["tables_used"].add("pragma_table_list")
        return get_virtual_table_rows("pragma_table_list", runtime)
    if pragma_name == "table_info":
        if not argument:
            return []
        runtime["tables_used"].add("pragma_table_info")
        return build_pragma_table_info(argument, runtime["datasets"])
    if pragma_name == "table_xinfo":
        if not argument:
            return []
        runtime["tables_used"].add("pragma_table_xinfo")
        return build_pragma_table_info(argument, runtime["datasets"])
    raise SandboxSqlError(f"Unsupported PRAGMA {pragma_name}")


def execute_show_create(statement: str, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    match = re.match(r"(?is)^show\s+create\s+table\s+([a-z_][\w.]*)$", collapse_whitespace(statement))
    if not match:
        raise SandboxSqlError("Unsupported SHOW CREATE syntax")
    table_name = match.group(1).lower()
    runtime["tables_used"].add(table_name)
    return [{"Table": table_name, "Create Table": build_create_sql(table_name, runtime["datasets"].get(table_name, []))}]


def execute_show_tables(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    runtime["tables_used"].add("show_tables")
    return [{"Tables_in_main": table_name} for table_name in sorted(runtime["datasets"].keys())]


def execute_describe(statement: str, runtime: dict[str, Any]) -> list[dict[str, Any]]:
    match = re.match(r"(?is)^desc(?:ribe)?\s+([a-z_][\w.]*)$", collapse_whitespace(statement))
    if not match:
        raise SandboxSqlError("Unsupported DESCRIBE syntax")
    table_name = match.group(1).lower()
    runtime["tables_used"].add(table_name)
    rows = build_pragma_table_info(table_name, runtime["datasets"])
    return [
        {
            "Field": row["name"],
            "Type": row["type"],
            "Null": "YES",
            "Key": "",
            "Default": None,
            "Extra": "",
        }
        for row in rows
    ]


def execute_sql_sandbox(
    sql: str,
    *,
    datasets: dict[str, list[dict[str, Any]]] | None = None,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prepared_sql = reconstruct_fragmented_keywords(expand_mysql_version_comments(normalize_mysql_backslash_quotes(sql or "")))
    quote_check_sql = strip_sql_comments(prepared_sql)
    if not has_balanced_quotes(quote_check_sql):
        raise SandboxSqlError("You have an error in your SQL syntax near an unterminated string literal")

    cleaned = collapse_whitespace(quote_check_sql)
    statements = split_top_level(cleaned, ";")
    if not statements:
        return {
            "rows": [],
            "query_log": [],
            "tables_used": set(),
            "union_used": False,
            "delay_ms": 0,
            "oob_events": [],
            "statements": [],
        }

    runtime = {
        "datasets": datasets or get_sandbox_datasets(),
        "variables": {key.lower(): value for key, value in (variables or {}).items()},
        "delay_ms": 0,
        "tables_used": set(),
        "query_log": [],
        "union_used": False,
        "oob_events": [],
    }
    runtime["variables"].setdefault("@@version", "mock-mysql-8.0.37-lab")
    runtime["variables"].setdefault("version", runtime["variables"]["@@version"])
    runtime["variables"].setdefault("sqlite_version", "3.45.1-lab")
    runtime["variables"].setdefault("sqlite_source_id", "2026-03-28 sandbox sqlite source id")
    runtime["variables"].setdefault("database", "main")
    runtime["variables"].setdefault("current_database", "main")
    runtime["variables"].setdefault("current_user", "lab_user")
    runtime["variables"].setdefault("user", "lab_user")
    runtime["variables"].setdefault("current_date", "2026-03-28")
    runtime["variables"].setdefault("current_time", "13:30:00")
    runtime["variables"].setdefault("current_timestamp", "2026-03-28 13:30:00")

    primary_rows: list[dict[str, Any]] = []
    last_rows: list[dict[str, Any]] = []

    for statement in statements:
        normalized = collapse_whitespace(statement)
        if not normalized:
            continue

        runtime["query_log"].append(normalized)
        lowered = normalized.lower()

        if lowered.startswith("select "):
            select_branches = parse_select(normalized)
            branch_rows: list[dict[str, Any]] = []
            if len(select_branches) > 1:
                runtime["union_used"] = True
                branch_widths = [infer_projection_width(branch, runtime) for branch in select_branches]
                if len(set(branch_widths)) != 1:
                    raise SandboxRuntimeError(
                        "The used SELECT statements have a different number of columns",
                        code="1222",
                        sqlstate="21000",
                    )
            for branch in select_branches:
                branch_rows.extend(execute_select_statement(branch, runtime))
            last_rows = branch_rows
            if not primary_rows:
                primary_rows = branch_rows
            continue

        if lowered.startswith("pragma "):
            pragma_rows = execute_pragma(normalized, runtime)
            last_rows = pragma_rows
            if not primary_rows:
                primary_rows = pragma_rows
            continue

        if lowered.startswith("show create table "):
            show_rows = execute_show_create(normalized, runtime)
            last_rows = show_rows
            if not primary_rows:
                primary_rows = show_rows
            continue

        if lowered.startswith("show tables"):
            show_rows = execute_show_tables(runtime)
            last_rows = show_rows
            if not primary_rows:
                primary_rows = show_rows
            continue

        if lowered.startswith("describe ") or lowered.startswith("desc "):
            describe_rows = execute_describe(normalized, runtime)
            last_rows = describe_rows
            if not primary_rows:
                primary_rows = describe_rows
            continue

        if lowered.startswith("insert "):
            table_name, columns, value_nodes = parse_insert(normalized)
            runtime["tables_used"].add(table_name)
            row = {}
            for index, column in enumerate(columns):
                row[column] = evaluate_expression(value_nodes[index], None, runtime)
            next_id = len(runtime["datasets"].setdefault(table_name, [])) + 1
            row.setdefault("id", next_id)
            runtime["datasets"][table_name].append(row)
            continue

        if lowered.startswith("update "):
            table_name, assignments, where_expr = parse_update(normalized)
            runtime["tables_used"].add(table_name)
            for row in runtime["datasets"].get(table_name, []):
                lowered_row = {key.lower(): value for key, value in row.items()}
                if where_expr is None or truthy(evaluate_expression(where_expr, lowered_row, runtime)):
                    for column, expression in assignments.items():
                        row[column] = evaluate_expression(expression, lowered_row, runtime)
            continue

        if lowered.startswith("delete from "):
            table_name, where_expr = parse_delete(normalized)
            runtime["tables_used"].add(table_name)
            retained_rows = []
            for row in runtime["datasets"].get(table_name, []):
                lowered_row = {key.lower(): value for key, value in row.items()}
                if where_expr is not None and truthy(evaluate_expression(where_expr, lowered_row, runtime)):
                    continue
                retained_rows.append(row)
            runtime["datasets"][table_name] = retained_rows
            continue

        if lowered.startswith("drop table "):
            table_name = collapse_whitespace(normalized[11:]).split(" ")[0].lower()
            runtime["tables_used"].add(table_name)
            runtime["datasets"].pop(table_name, None)
            continue

        raise SandboxSqlError(f"Unsupported statement: {normalized}")

    return {
        "rows": last_rows or primary_rows,
        "query_log": runtime["query_log"],
        "tables_used": runtime["tables_used"],
        "union_used": runtime["union_used"],
        "delay_ms": runtime["delay_ms"],
        "oob_events": runtime["oob_events"],
        "statements": statements,
        "datasets": runtime["datasets"],
    }
