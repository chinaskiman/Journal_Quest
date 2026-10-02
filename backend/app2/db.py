"""SQLAlchemy engine / session setup for the v2 database (SQLite, WAL).

The v2 database is a fresh, empty database (``tradequest_v2.db``) that is fully
separate from the legacy v1 file.  Tables are created with ``create_all`` only
when missing; an existing v2 database is never silently dropped or overwritten.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def _ensure_schema_upgrades(conn) -> None:
    """Idempotent, additive-only column upgrades for existing v2 databases.

    ``create_all`` never alters existing tables, so columns added after a
    database was first created are back-filled here with plain ALTER TABLE
    (nullable, no default) - historical rows simply keep NULL.
    """
    cols = {row[1] for row in conn.exec_driver_sql(
        "PRAGMA table_info(weekly_reviews)").fetchall()}
    if cols and "advice_to_future_me" not in cols:
        conn.exec_driver_sql(
            "ALTER TABLE weekly_reviews ADD COLUMN advice_to_future_me TEXT")


def initialize_db() -> bool:
    """Create tables if they do not exist yet.

    Returns True when the database file was created fresh (first run).
    Initialization is deterministic and repeatable; it never drops data.
    """
    fresh = not config.DB_PATH.exists()
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _ensure_schema_upgrades(conn)
    if fresh:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO app_meta (key, value) "
                    "VALUES ('schema_version', '2')"
                )
            )
    return fresh


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
