"""Import / export endpoints."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import exporter
from ..analytics import build_analytics
from ..db import get_db
from ..importer import import_workbook
from ..models import OptionValue
from ..serializers import serialize_trades
from ..schemas import ImportReportOut

router = APIRouter(prefix="/api/io", tags=["import-export"])


def _xlsx_response(content: bytes, filename: str) -> StreamingResponse:
    import io

    return StreamingResponse(
        io.BytesIO(content),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ImportReportOut)
async def import_file(
    file: UploadFile,
    mode: str = "replace",
    db: Session = Depends(get_db),
):
    if mode not in ("replace", "merge"):
        raise HTTPException(422, "mode must be 'replace' or 'merge'")
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(422, "Only .xlsx files are supported")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        report = import_workbook(tmp_path, db, mode=mode)
    except Exception as exc:  # noqa: BLE001 - surface a clean 422
        raise HTTPException(422, f"Import failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return ImportReportOut(
        trades_imported=report.trades_imported,
        options_imported=report.options_imported,
        mode=report.mode,
        workbook=Path(file.filename).name,
    )


@router.get("/export/journal")
def export_journal(db: Session = Depends(get_db)):
    return _xlsx_response(exporter.export_journal_xlsx(db), "tradequest-journal.xlsx")


@router.get("/export/analytics")
def export_analytics(db: Session = Depends(get_db)):
    from ..models import Trade

    trades = db.query(Trade).order_by(Trade.seq, Trade.id).all()
    rows = serialize_trades(trades)
    option_lists: dict[str, list[str]] = {}
    for option in (
        db.query(OptionValue).order_by(OptionValue.list_key, OptionValue.position, OptionValue.id)
    ):
        option_lists.setdefault(option.list_key, []).append(option.value)
    payload = build_analytics(rows, option_lists)
    content = exporter.export_analytics_xlsx(db, payload)
    return _xlsx_response(content, "tradequest-analytics.xlsx")


@router.get("/export/backup")
def export_backup(db: Session = Depends(get_db)):
    return _xlsx_response(exporter.export_backup_xlsx(db), "tradequest-backup.xlsx")
