from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..db import ensure_user, fetch_completed_challenges, record_completion
from ..services.catalog import build_bootstrap_payload, get_category, get_challenge, get_challenge_public
from ..services.console import execute_console_query
from ..services.simulation import reset_challenge_state, simulate


api_bp = Blueprint("api", __name__)


def current_user_id() -> str:
    payload = request.get_json(silent=True) or {}
    return (
        request.args.get("user_id")
        or payload.get("user_id")
        or request.headers.get("X-User-Id")
        or "local-trainee"
    )


@api_bp.get("/health")
def healthcheck():
    return jsonify({"status": "ok"})


@api_bp.get("/bootstrap")
def bootstrap():
    user_id = current_user_id()
    ensure_user(user_id)
    completed = fetch_completed_challenges(user_id)
    return jsonify(build_bootstrap_payload(completed))


@api_bp.post("/console/execute")
def execute_console():
    payload = request.get_json(silent=True) or {}
    return jsonify(execute_console_query(payload.get("query", "")))


@api_bp.get("/categories/<slug>")
def category_detail(slug: str):
    user_id = current_user_id()
    ensure_user(user_id)
    completed = fetch_completed_challenges(user_id)
    category = get_category(slug, completed)
    if category is None:
        return jsonify({"error": "Category not found"}), 404
    return jsonify(category)


@api_bp.get("/challenges/<challenge_id>")
def challenge_detail(challenge_id: str):
    user_id = current_user_id()
    ensure_user(user_id)
    completed = fetch_completed_challenges(user_id)
    challenge = get_challenge_public(challenge_id, completed)
    if challenge is None:
        return jsonify({"error": "Challenge not found"}), 404
    return jsonify(challenge)


@api_bp.post("/challenges/<challenge_id>/simulate")
def simulate_challenge(challenge_id: str):
    user_id = current_user_id()
    ensure_user(user_id)
    challenge = get_challenge(challenge_id)
    if challenge is None:
        return jsonify({"error": "Challenge not found"}), 404

    payload = request.get_json(silent=True) or {}
    inputs = payload.get("inputs", {})
    result = simulate(challenge, inputs, user_id)

    if result["solved"]:
        record_completion(user_id, challenge_id, result["flag"])

    completed = fetch_completed_challenges(user_id)
    return jsonify(
        {
            "challenge": get_challenge_public(challenge_id, completed),
            "result": result,
            "bootstrap": build_bootstrap_payload(completed),
        }
    )


@api_bp.post("/challenges/<challenge_id>/reset")
def reset_challenge(challenge_id: str):
    user_id = current_user_id()
    ensure_user(user_id)
    reset_challenge_state(user_id, challenge_id)
    return jsonify({"status": "reset", "challenge_id": challenge_id})
