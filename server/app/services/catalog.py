from __future__ import annotations

from copy import deepcopy

from ..data.challenges import CATEGORIES as LEGACY_CATEGORIES
from ..data.lab_catalog import CATEGORIES as PRIMARY_CATEGORIES
from ..data.mock_data import get_dataset_preview


CATEGORY_RESTORE_SLUGS = {
    "error-based",
    "boolean-blind",
    "time-based",
    "stacked-query",
}


LOGIN_UNSAFE_QUERY = "SELECT id, username, role FROM users WHERE username = '<username>' AND password = '<password>';"
LOGIN_SAFE_QUERY = "SELECT id, username, role FROM users WHERE username = ? AND password = ?;"
LOGIN_DEFENSE = [
    "Sử dụng prepared statements cho username và password.",
    "Không ghép input vào login query.",
]


def build_login_round_level(
    level_number: int,
    title: str,
    difficulty: str,
    objective: str,
    focus: str,
    success_explanation: str,
    flag: str,
    filter_variant: str,
) -> dict:
    return {
        "id": f"login-bypass-l{level_number}",
        "level": level_number,
        "title": title,
        "difficulty": difficulty,
        "objective": objective,
        "focus": focus,
        "fields": [
            {"name": "username", "label": "Username", "placeholder": "", "default_value": "", "multiline": False},
            {"name": "password", "label": "Password", "placeholder": "", "default_value": "", "multiline": False},
        ],
        "unsafe_query": LOGIN_UNSAFE_QUERY,
        "safe_query": LOGIN_SAFE_QUERY,
        "hint": "",
        "success_explanation": success_explanation,
        "defense": LOGIN_DEFENSE,
        "flag": flag,
        "simulation": {"type": "login_flow", "filter_variant": filter_variant},
        "preview_datasets": ["users"],
    }


LOGIN_ROUNDS_CATEGORY = {
    "slug": "login-bypass",
    "title": "Login",
    "difficulty": "Intermediate",
    "summary": "Login bypass lab with one no-filter baseline and seven blacklist rounds.",
    "accent": "red",
    "levels": [
        build_login_round_level(
            1,
            "Level 1 - No filter",
            "Beginner",
            "Backend nhận trực tiếp username và password, không có bộ lọc nào trước khi ghép query.",
            "No filter",
            "Không có bộ lọc nào nên tautology có thể tác động trực tiếp lên query đăng nhập.",
            "HCSC{login_no_filter}",
            "no_filter",
        ),
        build_login_round_level(
            2,
            "Round 1 - Filter: or",
            "Beginner",
            "Backend lọc token or trước khi ghép username vào query đăng nhập.",
            "Filter: or",
            "Chỉ chặn token or không đủ để khóa các biểu thức logic tương đương trong SQL.",
            "HCSC{login_round_1}",
            "login_round_1",
        ),
        build_login_round_level(
            3,
            "Round 2 - Filter: or, and, like, =, --",
            "Beginner",
            "Backend lọc các token or, and, like, =, -- khỏi username.",
            "Filter: or, and, like, =, --",
            "Ngay cả khi chặn một cụm keyword phổ biến, SQL vẫn còn nhiều toán tử và separator khác.",
            "HCSC{login_round_2}",
            "login_round_2",
        ),
        build_login_round_level(
            4,
            "Round 3 - Filter: or, and, =, like, >, <, --, /*, */",
            "Intermediate",
            "Backend lọc thêm các toán tử so sánh và comment marker nhưng vẫn ghép input vào query.",
            "Filter: or, and, =, like, >, <, --, /*, */",
            "Comment blacklist và operator blacklist vẫn để lại các cách biểu diễn logic khác cho SQL.",
            "HCSC{login_round_3}",
            "login_round_3",
        ),
        build_login_round_level(
            5,
            "Round 4 - Filter: or, and, =, like, >, <, --, /*, */, admin",
            "Intermediate",
            "Backend bổ sung filter admin vào blacklist nhưng vẫn để logic query bị điều khiển bởi input.",
            "Filter: or, and, =, like, >, <, --, /*, */, admin",
            "Chặn tên admin dạng plain-text không ngăn được việc trả về dòng admin qua tautology.",
            "HCSC{login_round_4}",
            "login_round_4",
        ),
        build_login_round_level(
            6,
            "Round 5 - Filter: or, and, =, like, >, <, --, /*, */, admin, union",
            "Advanced",
            "Backend bổ sung thêm union vào blacklist nhưng vẫn ghép thẳng username vào login query.",
            "Filter: or, and, =, like, >, <, --, /*, */, admin, union",
            "Union không cần thiết cho login bypass; nếu vẫn ghép input vào WHERE thì tautology vẫn đủ để lấy admin row.",
            "HCSC{login_round_5}",
            "login_round_5",
        ),
        build_login_round_level(
            7,
            "Round 6 - Filter: or, and, true, false, union, like, =, >, <, ;, --, /*, */, admin",
            "Advanced",
            "Backend chạy blacklist token nghiêm ngặt hơn trên raw input username.",
            "Filter: or, and, true, false, union, like, =, >, <, ;, --, /*, */, admin",
            "Ngay cả blacklist dài vẫn bỏ sót các toán tử và hàm khác nếu app tiếp tục ghép input vào SQL.",
            "HCSC{login_round_6}",
            "login_round_6",
        ),
        build_login_round_level(
            8,
            "Round 7 - Final WAF blacklist",
            "Advanced",
            "Cùng blacklist như round 6, nhưng backend URL-decode một lần trước khi lọc signature.",
            "Filter: or, and, true, false, union, like, =, >, <, ;, --, /*, */, admin",
            "Nếu WAF và backend không canonicalize giống nhau, payload encoded vẫn có thể trở lại thành SQL hợp lệ ở lớp thực thi.",
            "HCSC{login_round_7}",
            "login_round_7",
        ),
    ],
}


CATEGORY_LEVEL_SELECTIONS = {
    "error-based": [2, 3, 4],
    "boolean-blind": [1, 2, 3],
    "time-based": [1, 2, 3],
    "stacked-query": [1, 2, 3],
    "second-order": [1, 2, 3, 4],
}


FILTER_VARIANT_NOTICES = {
    "login_round_1": "Đang lọc token: or",
    "login_round_2": "Đang lọc token: or, and, like, =, --",
    "login_round_3": "Đang lọc token: or, and, =, like, >, <, --, /*, */",
    "login_round_4": "Đang lọc token: or, and, =, like, >, <, --, /*, */, admin",
    "login_round_5": "Đang lọc token: or, and, =, like, >, <, --, /*, */, admin, union",
    "login_round_6": "Đang lọc token: or, and, true, false, union, like, =, >, <, ;, --, /*, */, admin",
    "login_round_7": "Đang lọc token sau 1 lần URL decode: or, and, true, false, union, like, =, >, <, ;, --, /*, */, admin",
    "block_quote": "Đang chặn ký tự: '",
    "block_quote_comment": "Đang chặn: ' và --",
    "block_quote_doublequote": "Đang chặn ký tự: ' và \"",
    "block_comment": "Đang chặn comment marker: --, #, /* */",
    "block_or_keyword": "Đang chặn keyword: OR",
    "block_select_keyword": "Đang chặn keyword: SELECT",
    "block_union_keyword": "Đang chặn keyword: UNION",
    "space_strip_filter": "Backend xóa dấu cách thường trong username trước khi ghép query.",
    "logical_filter_strip": "Backend xóa OR/AND bằng regex không đệ quy.",
    "equality_filter_strip": "Backend xóa ký tự = trước khi ghép query.",
    "quote_escape_filter": "Backend escape quote nhưng vẫn có thể bị trailing backslash abuse.",
    "comment_filter_strip": "Backend xóa các comment marker như --, #, /* */.",
    "case_sensitive_or_strip": "Backend chỉ xóa đúng chữ thường 'or'.",
    "non_recursive_or_filter": "Backend xóa OR một lượt, không phân tích lại chuỗi sau khi thay thế.",
    "string_char_filter": "Backend chặn direct token kiểu chữ cái như admin, nhưng không hiểu hex literal.",
    "login_waf_signature": "WAF chỉ quét signature SQLi dạng plain-text trước khi backend URL-decode.",
    "hpp_override": "WAF nhìn tham số đầu, backend lại lấy giá trị user cuối cùng.",
    "strict_logical_block": "Backend chặn OR, AND, ||, && bằng regex.",
    "space_comment_block": "Backend chặn đồng thời khoảng trắng và comment marker.",
    "null_byte_filter": "Bộ kiểm tra chỉ nhìn phần trước null byte, nhưng query ghép cả chuỗi xuống backend.",
    "regex_filter": "Đang chặn theo regex các mẫu: UNION SELECT, OR 1=1, ', --, /*",
    "waf_filter": "Đang chặn sau decode/comment-strip các mẫu: UNION SELECT, SLEEP(), BENCHMARK()",
    "encode_filter": "Đang chặn sau 1 lần decode: UNION, SELECT, --, '",
    "case_sensitive_filter": "Đang chặn dạng viết hoa: UNION và SELECT",
    "space_filter": "Đang chặn ký tự khoảng trắng.",
    "advanced_parser": "Đang chặn sau canonicalization: UNION SELECT, dấu nháy đơn và tautology.",
    "login_blacklist": "Đang chặn blacklist: ', \", OR, UNION, SELECT, --, /* và dấu cách.",
    "login_waf": "WAF decode một lần rồi chặn quote, OR, UNION và SELECT ở dạng phổ biến.",
}


def clone_category_with_slug(category: dict, new_slug: str, new_title: str | None = None) -> dict:
    cloned = deepcopy(category)
    cloned["slug"] = new_slug
    if new_title is not None:
        cloned["title"] = new_title

    for index, level in enumerate(cloned["levels"], start=1):
        level["id"] = f"{new_slug}-l{index}"

    return cloned


def clone_category_with_levels(category: dict, selected_levels: list[int], new_slug: str | None = None, new_title: str | None = None) -> dict:
    cloned = deepcopy(category)
    cloned["slug"] = new_slug or cloned["slug"]
    if new_title is not None:
        cloned["title"] = new_title

    chosen_levels = [level for level in cloned["levels"] if level["level"] in selected_levels]
    normalized_levels = []
    for new_level, original_level in enumerate(chosen_levels, start=1):
        level_copy = deepcopy(original_level)
        level_copy["level"] = new_level
        level_copy["id"] = f"{cloned['slug']}-l{new_level}"
        level_copy["title"] = level_copy["title"].replace(
            f"Level {original_level['level']} -",
            f"Level {new_level} -",
            1,
        )
        normalized_levels.append(level_copy)

    cloned["levels"] = normalized_levels
    return cloned


CATEGORIES = [
    LOGIN_ROUNDS_CATEGORY,
    *[category for category in PRIMARY_CATEGORIES if category["slug"] not in {"login-bypass", "second-order"}],
    *[
        clone_category_with_levels(category, CATEGORY_LEVEL_SELECTIONS[category["slug"]])
        if category["slug"] in CATEGORY_LEVEL_SELECTIONS
        else category
        for category in LEGACY_CATEGORIES
        if category["slug"] in CATEGORY_RESTORE_SLUGS
    ],
    *[
        clone_category_with_levels(
            category,
            CATEGORY_LEVEL_SELECTIONS["second-order"],
            new_slug="second-order-classic",
            new_title="Second-order",
        )
        for category in LEGACY_CATEGORIES
        if category["slug"] == "second-order"
    ],
]


def get_filter_notice(challenge: dict) -> str | None:
    simulation = challenge.get("simulation", {})
    filter_variant = simulation.get("filter_variant") or simulation.get("variant")
    if not filter_variant or filter_variant == "no_filter":
        return None
    return FILTER_VARIANT_NOTICES.get(filter_variant)


CATEGORY_INDEX = {category["slug"]: category for category in CATEGORIES}
CHALLENGE_INDEX = {
    challenge["id"]: {
        **challenge,
        "category_slug": category["slug"],
        "category_title": category["title"],
        "category_difficulty": category["difficulty"],
        "category_accent": category["accent"],
    }
    for category in CATEGORIES
    for challenge in category["levels"]
}


def serialize_challenge(challenge: dict, completed: dict[str, dict[str, str]]) -> dict:
    payload = deepcopy(challenge)
    payload["completed"] = challenge["id"] in completed
    payload["completed_at"] = completed.get(challenge["id"], {}).get("completed_at")
    payload["filter_notice"] = get_filter_notice(challenge)

    preview_tables = []
    for dataset_name in challenge.get("preview_datasets", []):
        preview_tables.append(
            {
                "name": dataset_name,
                "rows": get_dataset_preview(dataset_name),
            }
        )

    payload["preview_tables"] = preview_tables
    payload.pop("simulation", None)
    payload.pop("flag", None)
    return payload


def get_category(slug: str, completed: dict[str, dict[str, str]]) -> dict | None:
    category = CATEGORY_INDEX.get(slug)
    if not category:
        return None

    levels = [serialize_challenge(level, completed) for level in category["levels"]]
    solved = sum(1 for level in levels if level["completed"])

    return {
        "slug": category["slug"],
        "title": category["title"],
        "difficulty": category["difficulty"],
        "summary": category["summary"],
        "accent": category["accent"],
        "levels": levels,
        "progress": {
            "solved": solved,
            "total": len(levels),
            "percent": round((solved / len(levels)) * 100),
        },
    }


def get_challenge(challenge_id: str) -> dict | None:
    return CHALLENGE_INDEX.get(challenge_id)


def get_challenge_public(challenge_id: str, completed: dict[str, dict[str, str]]) -> dict | None:
    challenge = CHALLENGE_INDEX.get(challenge_id)
    if not challenge:
        return None
    return serialize_challenge(challenge, completed)


def get_catalog_summary(completed: dict[str, dict[str, str]]) -> list[dict]:
    summaries = []

    for category in CATEGORIES:
        levels = [serialize_challenge(level, completed) for level in category["levels"]]
        solved = sum(1 for level in levels if level["completed"])
        summaries.append(
            {
                "slug": category["slug"],
                "title": category["title"],
                "difficulty": category["difficulty"],
                "summary": category["summary"],
                "accent": category["accent"],
                "levels": levels,
                "progress": {
                    "solved": solved,
                    "total": len(levels),
                    "percent": round((solved / len(levels)) * 100),
                },
            }
        )

    return summaries


def build_bootstrap_payload(completed: dict[str, dict[str, str]]) -> dict:
    categories = get_catalog_summary(completed)
    total_levels = sum(category["progress"]["total"] for category in categories)
    solved_levels = sum(category["progress"]["solved"] for category in categories)
    completed_categories = sum(
        1 for category in categories if category["progress"]["total"] == category["progress"]["solved"]
    )

    return {
        "categories": categories,
        "stats": {
            "solved_levels": solved_levels,
            "total_levels": total_levels,
            "completed_categories": completed_categories,
            "total_categories": len(categories),
        },
    }
