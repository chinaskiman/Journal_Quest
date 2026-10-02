"""Create the database and seed it from the Excel workbook (if present).

Usage:
    python scripts/bootstrap.py            # import once (idempotent)
    python scripts/bootstrap.py --force    # wipe + re-import
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import EXCEL_PATH  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.importer import import_workbook  # noqa: E402
from app.models import Trade  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the TradeQuest database")
    parser.add_argument("--force", action="store_true", help="wipe and re-import")
    parser.add_argument("--excel", default=str(EXCEL_PATH), help="workbook path")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if args.force:
            n = db.query(Trade).delete()
            db.commit()
            print(f"[bootstrap] wiped {n} existing trades")

        existing = db.query(Trade).count()
        if existing and not args.force:
            print(f"[bootstrap] database already contains {existing} trades - nothing to do")
            return

        report = import_workbook(args.excel, db, mode="replace")
        print(
            f"[bootstrap] imported {report.trades_imported} trades and "
            f"{report.options_imported} option values from {report.workbook}"
        )


if __name__ == "__main__":
    main()
