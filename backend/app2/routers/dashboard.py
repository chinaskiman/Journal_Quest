"""Dashboard (Quest Hub) and system endpoints."""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..services import dashboard as dashboard_service
from ..services.activity import run_progress_engine

router = APIRouter(prefix="/api", tags=["dashboard"])

system_router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """Accurate persisted summary.  Empty DB returns honest empty states.

    Runs the full progress engine (streak detection -> recovery -> quests ->
    achievements) and commits, exactly like the other gamification reads, so
    opening the Quest Hub is a reliable trigger for streak evaluation instead of
    depending on a prior write.
    """
    run_progress_engine(db)
    db.commit()
    return dashboard_service.dashboard_summary(db)


@system_router.get("/health")
def health():
    return {
        "status": "ok",
        "app": "Trade Quest v2",
        "host": config.HOST,  # always 127.0.0.1 - local-first by design
    }


@system_router.get("/backup")
def create_backup():
    """Copy the SQLite database to data/backups/ (timestamped, last 10 kept).

    Uses SQLite's backup API for consistency (safe while the server runs).
    """
    import sqlite3

    if not config.DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    timestamp = config.now_local().strftime("%Y%m%d_%H%M%S")
    target = config.BACKUP_DIR / f"tradequest_v2_{timestamp}.db"
    src = sqlite3.connect(str(config.DB_PATH))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    # prune old backups beyond MAX_BACKUPS (oldest first)
    backups = sorted(config.BACKUP_DIR.glob("tradequest_v2_*.db"))
    for old in backups[: max(0, len(backups) - config.MAX_BACKUPS)]:
        old.unlink(missing_ok=True)
    return {"backup": target.name, "kept": config.MAX_BACKUPS}


@system_router.get("/backups")
def list_backups():
    backups = sorted(config.BACKUP_DIR.glob("tradequest_v2_*.db"), reverse=True)
    return {"items": [b.name for b in backups]}
