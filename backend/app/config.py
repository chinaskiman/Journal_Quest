"""Application configuration.

Every path can be overridden with an environment variable so tests and
scripts can point at isolated databases:

  TRADEQUEST_DB      - SQLite database file
  TRADEQUEST_EXCEL   - source workbook used for the initial import
  TRADEQUEST_CORS    - comma separated list of allowed CORS origins
"""
from __future__ import annotations

import os
from pathlib import Path

# backend/app/config.py -> parents[2] is the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_EXCEL_NAME = "Trading Journla-Reaction Based Strategy.xlsx"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value).resolve() if value else default


DB_PATH = _env_path("TRADEQUEST_DB", DATA_DIR / "tradequest.db")
EXCEL_PATH = _env_path("TRADEQUEST_EXCEL", PROJECT_ROOT / DEFAULT_EXCEL_NAME)

DB_URL = os.environ.get("TRADEQUEST_DB_URL") or f"sqlite:///{DB_PATH}"

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "TRADEQUEST_CORS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
    ).split(",")
    if origin.strip()
]
