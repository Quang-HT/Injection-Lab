export function getChallengeId(categorySlug, level) {
  return `${categorySlug}-l${level}`;
}

export function getCategoryPath(category) {
  const nextLevel = category?.levels?.find((level) => !level.completed) ?? category?.levels?.[0];
  return nextLevel ? `/lab/${category.slug}/${nextLevel.level}` : "/";
}

const NAV_LABELS = {
  "login-bypass": "Login",
  "union-based": "Union",
  "out-of-band": "OOB",
  "error-based": "Error",
  "boolean-blind": "Boolean",
  "time-based": "Time",
  "stacked-query": "Stacked",
  prevention: "Prevention",
  "second-order-classic": "Second-order",
};

export function getCategoryNavLabel(category) {
  return NAV_LABELS[category.slug] ?? category.title;
}

const PAGE_TITLES = {
  "login-bypass": "Login",
  "union-based": "Union",
  "out-of-band": "Out of Band",
  "error-based": "Error",
  "boolean-blind": "Boolean",
  "time-based": "Time",
  "stacked-query": "Stacked",
  prevention: "Prevention",
  "second-order-classic": "Second-order",
};

export function getLabPageTitle(challenge) {
  return PAGE_TITLES[challenge?.category_slug] ?? challenge?.category_title ?? challenge?.title ?? "Lab";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

const USER_INPUT_OPEN = "\uE000";
const USER_INPUT_CLOSE = "\uE001";
const SQL_KEYWORD_PATTERN =
  /\b(SELECT|FROM|WHERE|AND|OR|INSERT|INTO|VALUES|UPDATE|SET|DELETE|DROP|TABLE|UNION|LIKE|LIMIT|COUNT|ORDER|BY|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|HAVING|AS|CASE|WHEN|THEN|ELSE|END|DISTINCT|EXISTS|IN|IS|NOT|DESC|ASC|SHOW|DESCRIBE|PRAGMA)\b/gi;

function wrapUserInput(value) {
  return `${USER_INPUT_OPEN}${value}${USER_INPUT_CLOSE}`;
}

function highlightPlainSql(text) {
  return escapeHtml(text)
    .replace(SQL_KEYWORD_PATTERN, (match) => `<span class="sql-keyword">${match}</span>`)
    .replace(/\b\d+\b/g, (match) => `<span class="sql-number">${match}</span>`);
}

function renderUserAwareText(text, renderer) {
  if (!text) {
    return "";
  }

  let output = "";
  let cursor = 0;

  while (cursor < text.length) {
    const start = text.indexOf(USER_INPUT_OPEN, cursor);
    if (start === -1) {
      output += renderer(text.slice(cursor));
      break;
    }

    output += renderer(text.slice(cursor, start));
    const end = text.indexOf(USER_INPUT_CLOSE, start + USER_INPUT_OPEN.length);
    const userText =
      end === -1
        ? text.slice(start + USER_INPUT_OPEN.length)
        : text.slice(start + USER_INPUT_OPEN.length, end);
    output += `<span class="sql-user-input">${escapeHtml(userText)}</span>`;
    cursor = end === -1 ? text.length : end + USER_INPUT_CLOSE.length;
  }

  return output;
}

function renderStringLiteral(text) {
  return renderUserAwareText(text, (segment) =>
    segment ? `<span class="sql-string">${escapeHtml(segment)}</span>` : "",
  );
}

function renderCommentLiteral(text) {
  return renderUserAwareText(text, (segment) =>
    segment ? `<span class="sql-comment">${escapeHtml(segment)}</span>` : "",
  );
}

export function highlightSql(query) {
  const source = String(query || "");
  let output = "";
  let index = 0;

  while (index < source.length) {
    const current = source[index];
    const next = source[index + 1] || "";

    if (current === "-" && next === "-") {
      let end = index + 2;
      while (end < source.length && source[end] !== "\n") {
        end += 1;
      }
      if (end < source.length) {
        end += 1;
      }
      output += renderCommentLiteral(source.slice(index, end));
      index = end;
      continue;
    }

    if (current === "#") {
      let end = index + 1;
      while (end < source.length && source[end] !== "\n") {
        end += 1;
      }
      if (end < source.length) {
        end += 1;
      }
      output += renderCommentLiteral(source.slice(index, end));
      index = end;
      continue;
    }

    if (current === "/" && next === "*") {
      let end = index + 2;
      while (end + 1 < source.length && !(source[end] === "*" && source[end + 1] === "/")) {
        end += 1;
      }
      end = end + 1 < source.length ? end + 2 : source.length;
      output += renderCommentLiteral(source.slice(index, end));
      index = end;
      continue;
    }

    if (current === "'") {
      let end = index + 1;
      while (end < source.length) {
        if (source[end] === "'" && source[end + 1] === "'") {
          end += 2;
          continue;
        }
        if (source[end] === "'") {
          end += 1;
          break;
        }
        end += 1;
      }
      output += renderStringLiteral(source.slice(index, end));
      index = end;
      continue;
    }

    let end = index;
    while (end < source.length) {
      const chunkCurrent = source[end];
      const chunkNext = source[end + 1] || "";
      if (
        chunkCurrent === "'" ||
        chunkCurrent === "#" ||
        (chunkCurrent === "-" && chunkNext === "-") ||
        (chunkCurrent === "/" && chunkNext === "*")
      ) {
        break;
      }
      end += 1;
    }

    output += renderUserAwareText(source.slice(index, end), highlightPlainSql);
    index = end;
  }

  return output;
}

export function buildSimulationQuery(challenge, inputs) {
  if (!challenge?.unsafe_query) {
    return "";
  }

  return Object.entries(inputs ?? {}).reduce((query, [name, value]) => {
    const safeValue = value === "" ? " " : value;
    return query.replaceAll(`<${name}>`, wrapUserInput(safeValue));
  }, challenge.unsafe_query);
}

function joinSections(parts) {
  return parts.filter(Boolean).join("\n\n");
}

export function formatAsciiTable(rows) {
  if (!rows?.length) {
    return "";
  }

  const columns = Object.keys(rows[0]);
  const widths = Object.fromEntries(
    columns.map((column) => [
      column,
      Math.max(column.length, ...rows.map((row) => String(row[column] ?? "NULL").length)),
    ]),
  );

  const border = `+${columns.map((column) => "-".repeat(widths[column] + 2)).join("+")}+`;
  const lines = [`Total: ${rows.length} row(s)`, border];

  rows.forEach((row) => {
    lines.push(
      `| ${columns
        .map((column) => String(row[column] ?? "NULL").padEnd(widths[column], " "))
        .join(" | ")} |`,
    );
    lines.push(border);
  });

  return lines.join("\n");
}

export function buildSimulationResultText(result) {
  if (!result) {
    return "";
  }

  if (result.mock_rows?.length) {
    return formatAsciiTable(result.mock_rows);
  }

  if (result.boolean_result === true) {
    return "TRUE";
  }

  if (result.boolean_result === false) {
    return "FALSE";
  }

  if (result.delay_ms) {
    return `Độ trễ mô phỏng: ${result.delay_ms} ms`;
  }

  if (result.query_log?.length) {
    return result.query_log.join("\n");
  }

  const dbLines = (result.terminal ?? [])
    .filter((line) => line.startsWith("[db]"))
    .map((line) => line.replace("[db] ", ""));
  if (dbLines.length) {
    return dbLines.join("\n");
  }

  return [result.headline, result.explanation].filter(Boolean).join("\n\n");
}

export function getVisibleFields(challenge) {
  if (!challenge?.fields?.length) {
    return [];
  }

  if (challenge.category_slug === "login-bypass") {
    return challenge.fields.filter((field) => field.name === "username" || field.name === "password");
  }

  if (challenge.fields.length > 1) {
    return challenge.fields;
  }

  const payloadField =
    challenge.fields.find((field) => field.name === "payload") ??
    challenge.fields.find((field) => field.name === "username") ??
    challenge.fields.find((field) => field.name === "fix") ??
    challenge.fields[0];

  return payloadField ? [payloadField] : [];
}

export function shouldUseManualSubmit(challenge) {
  return (
    challenge?.category_slug === "login-bypass" ||
    (challenge?.fields?.length ?? 0) > 1 ||
    challenge?.fields?.some((field) => field.multiline)
  );
}

export function shouldShowResultBox(challenge) {
  return challenge?.category_slug !== "time-based";
}

export function shouldShowQueryPreview(challenge) {
  if (!challenge) {
    return true;
  }

  if (challenge.category_slug === "union-based" && challenge.level > 1) {
    return false;
  }

  return true;
}

export function getInputLabel(challenge, visibleFields, formValues) {
  if (!challenge) {
    return "Ô nhập payload";
  }

  if (challenge.category_slug === "login-bypass") {
    return "Thông tin đăng nhập";
  }

  if (challenge.category_slug === "union-based") {
    const value = formValues.payload ?? "";
    return `Nhập id sản phẩm (độ dài: ${value.length})`;
  }

  const firstField = visibleFields[0];
  if (!firstField) {
    return "Ô nhập payload";
  }

  const value = formValues[firstField.name] ?? "";
  return `${firstField.label} (độ dài: ${value.length})`;
}

export function getResultTitle(challenge) {
  return challenge?.category_slug === "login-bypass" ? "Kết quả đăng nhập:" : "Kết quả:";
}

export function getFlagTitle() {
  return "Flag:";
}

export function buildCategoryResult(challenge, result, inputs) {
  if (!challenge || !result) {
    return "";
  }

  const tableText = buildSimulationResultText(result);

  switch (challenge.category_slug) {
    case "login-bypass":
      return joinSections([
        result.display_message ||
          `Đăng nhập thất bại với username là ${inputs.username || " "}, password là ${inputs.password || " "}.`,
        tableText,
      ]);
    case "union-based":
    case "second-order-classic":
      return joinSections([result.display_message, result.state_message, tableText]);
    default:
      return joinSections([result.display_message, result.state_message, tableText]);
  }
}
