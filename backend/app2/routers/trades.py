"""Trade journal + Quick Capture endpoints.

XP policy enforced here:
* Trade CREATE awards +20 XP (``capture:{trade_id}``) transactionally.
* Trade CLOSE, EDIT, DELETE award ZERO XP.
* ``user_pnl`` is stored verbatim (manual entry) and never affects any
  progression, quest or achievement.
* Results (win/loss/breakeven) are entered manually - never computed.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Trade
from ..schemas import (
    TradeClose,
    TradeCreate,
    TradeListOut,
    TradeMutationOut,
    TradeOut,
    TradeUpdate,
)
from ..services import quests as quests_service
from ..services import screenshots as screenshots_service
from ..services import xp as xp_service
from ..services.activity import run_progress_engine

router = APIRouter(prefix="/api/trades", tags=["trades"])

_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _get_trade(db: Session, trade_id: int, *, allow_deleted: bool = False) -> Trade:
    trade = db.get(Trade, trade_id)
    if trade is None or (trade.deleted_at is not None and not allow_deleted):
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


def _validate_symbol(db: Session, payload) -> None:
    """Symbols/setups must exist in settings *unless* exact snapshot exists."""
    from ..models import Setup, Symbol
    if payload.symbol is not None:
        exists = db.query(Symbol).filter(
            Symbol.name == payload.symbol, Symbol.is_active == 1).first()
        if not exists:
            raise HTTPException(
                status_code=422,
                detail=f"Symbol '{payload.symbol}' is not in Settings. "
                       "Create it first under Settings -> Symbols.",
            )
    if getattr(payload, "setup", None):
        exists = db.query(Setup).filter(
            Setup.name == payload.setup, Setup.is_active == 1).first()
        if not exists:
            raise HTTPException(
                status_code=422,
                detail=f"Setup '{payload.setup}' is not in Settings. "
                       "Create it first under Settings -> Setups.",
            )


@router.get("", response_model=TradeListOut)
def list_trades(
    status: str | None = None,
    symbol: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(Trade)
    if not include_deleted:
        q = q.filter(Trade.deleted_at.is_(None))
    if status:
        if status not in ("open", "closed"):
            raise HTTPException(status_code=422, detail="status must be open|closed")
        q = q.filter(Trade.status == status)
    if symbol:
        q = q.filter(Trade.symbol_label == symbol)
    total = q.count()
    rows = (
        q.order_by(Trade.opened_at.desc(), Trade.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TradeListOut(
        rows=[TradeOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=TradeMutationOut, status_code=201)
def create_trade(payload: TradeCreate, db: Session = Depends(get_db)) -> TradeMutationOut:
    _validate_symbol(db, payload)
    pre_total = xp_service.total_xp(db)
    trade = Trade(
        status=payload.status,
        symbol_label=payload.symbol,
        setup_label=payload.setup,
        direction=payload.direction,
        opened_at=payload.opened_at,
        closed_at=payload.closed_at,
        result=payload.result,
        result_note=payload.result_note,
        entry_price=payload.entry_price,
        exit_price=payload.exit_price,
        user_pnl=payload.user_pnl,
        screenshot_path=payload.screenshot_path,
        thesis=payload.thesis,
        notes=payload.notes,
    )
    db.add(trade)
    db.flush()  # trade.id available; still inside the transaction
    awarded = xp_service.award_xp(
        db,
        event_type="trade_create",
        amount=config.XP_TRADE_CREATE,
        idempotency_key=f"capture:{trade.id}",
        entity_type="trade",
        entity_id=trade.id,
    )
    run_progress_engine(db)
    db.commit()
    db.refresh(trade)
    out = TradeMutationOut.model_validate(trade)
    fb = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    out.xp_awarded = fb["xp_awarded"]
    out.level_up = fb["level_up"]
    return out

@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    return TradeOut.model_validate(_get_trade(db, trade_id))


@router.patch("/{trade_id}", response_model=TradeOut)
def update_trade(trade_id: int, payload: TradeUpdate,
                 db: Session = Depends(get_db)):
    """Edit a trade. Awards ZERO XP (ledger is append-only, nothing inserted)."""
    trade = _get_trade(db, trade_id)
    data = payload.model_dump(exclude_unset=True)
    if "symbol" in data:
        if data["symbol"] is None or data["symbol"] == "":
            raise HTTPException(status_code=422, detail="symbol cannot be emptied")
        _validate_symbol(db, payload)
        trade.symbol_label = data["symbol"]
    if "setup" in data:
        if data["setup"]:
            _validate_symbol(db, payload)
        trade.setup_label = data["setup"] or None
    for field in ("direction", "opened_at", "closed_at", "result", "result_note",
                  "entry_price", "exit_price", "user_pnl", "screenshot_path",
                  "thesis", "notes"):
        if field in data:
            setattr(trade, field, data[field])
    db.commit()
    db.refresh(trade)
    return TradeOut.model_validate(trade)


@router.post("/{trade_id}/close", response_model=TradeOut)
def close_trade(trade_id: int, payload: TradeClose,
                db: Session = Depends(get_db)):
    """Manual close. Awards ZERO XP by design (habit XP is for journaling)."""
    trade = _get_trade(db, trade_id)
    if trade.status == "closed":
        raise HTTPException(status_code=409, detail="Trade is already closed")
    trade.status = "closed"
    trade.closed_at = payload.closed_at or config.now_local()
    if payload.exit_price is not None:
        trade.exit_price = payload.exit_price
    if payload.user_pnl is not None:
        trade.user_pnl = payload.user_pnl
    if payload.result is not None:
        trade.result = payload.result
    if payload.result_note is not None:
        trade.result_note = payload.result_note
    db.commit()
    db.refresh(trade)
    return TradeOut.model_validate(trade)


@router.delete("/{trade_id}", status_code=204)
def delete_trade(trade_id: int, hard: bool = Query(False),
                 db: Session = Depends(get_db)):
    """Soft delete by default (XP ledger untouched - no clawback)."""
    trade = _get_trade(db, trade_id)
    if hard:
        db.delete(trade)
    else:
        trade.deleted_at = config.now_local()
    db.commit()
    return None


@router.get("/{trade_id}/screenshot")
def serve_screenshot(trade_id: int, db: Session = Depends(get_db)):
    """Serve the user-supplied screenshot path with strict validation.

    Defense in depth (all checks must pass):
    1. the trade exists and has a screenshot path;
    2. the path is absolute;
    3. the extension is an image type from the whitelist;
    4. the RESOLVED path (symlinks/junctions/``..``/8.3 aliases expanded)
       is inside one of the explicitly configured permitted directories
       (``TRADEQUEST2_SCREENSHOT_DIRS``; fail-closed when unconfigured) -
       no arbitrary local file exposure;
    5. the file exists and is at most 25 MB.
    """
    trade = _get_trade(db, trade_id)
    if not trade.screenshot_path:
        raise HTTPException(status_code=404, detail="Trade has no screenshot")
    path = Path(trade.screenshot_path)
    if not path.is_absolute():
        raise HTTPException(status_code=422, detail="Screenshot path must be absolute")
    if path.suffix.lower() not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=422, detail="Unsupported image type")
    allowed_dirs = config.screenshot_allowed_dirs()
    if not allowed_dirs:
        raise HTTPException(
            status_code=422,
            detail="No screenshot directories configured on the server "
                   "(set TRADEQUEST2_SCREENSHOT_DIRS)",
        )
    if not screenshots_service.is_permitted(trade.screenshot_path, allowed_dirs):
        raise HTTPException(
            status_code=422,
            detail="Screenshot path is outside the permitted directories",
        )
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot file not found on disk")
    if path.stat().st_size > 25 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Screenshot file too large")
    return FileResponse(path)

