from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "training-lab-dev-key")
    DATABASE_PATH = os.getenv(
        "TRAINING_LAB_DB",
        str(INSTANCE_DIR / "training_lab.sqlite3"),
    )
    CORS_ORIGINS = [origin.strip() for origin in os.getenv("CLIENT_ORIGIN", "http://localhost:5173").split(",")]
