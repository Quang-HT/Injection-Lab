from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS completed_challenges (
    user_id TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    flag TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, challenge_id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE_PATH"])
        connection.row_factory = sqlite3.Row
        g.db = connection
    return g.db


def close_db(_: Any = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_schema() -> None:
    database = get_db()
    database.executescript(SCHEMA)
    database.commit()


def init_app(app) -> None:
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)

    @app.teardown_appcontext
    def teardown_db(exception: Any = None) -> None:
        close_db(exception)

    with app.app_context():
        init_schema()


def ensure_user(user_id: str, display_name: str = "Local Trainee") -> None:
    database = get_db()
    database.execute(
        """
        INSERT OR IGNORE INTO users (id, display_name)
        VALUES (?, ?)
        """,
        (user_id, display_name),
    )
    database.commit()


def fetch_completed_challenges(user_id: str) -> dict[str, dict[str, str]]:
    database = get_db()
    rows = database.execute(
        """
        SELECT challenge_id, flag, completed_at
        FROM completed_challenges
        WHERE user_id = ?
        ORDER BY completed_at DESC
        """,
        (user_id,),
    ).fetchall()

    return {
        row["challenge_id"]: {
            "flag": row["flag"],
            "completed_at": row["completed_at"],
        }
        for row in rows
    }


def record_completion(user_id: str, challenge_id: str, flag: str) -> None:
    database = get_db()
    database.execute(
        """
        INSERT OR IGNORE INTO completed_challenges (user_id, challenge_id, flag)
        VALUES (?, ?, ?)
        """,
        (user_id, challenge_id, flag),
    )
    database.commit()
