"""Daily and Weekly Review endpoints.

* Daily Review: one per local calendar date, +15 XP, key ``daily:{date}``.
* Weekly Review: one per ISO week, +30 XP, key ``weekly:{iso_year-week}``.
* Both use stable idempotency keys so edits/retries/restarts cannot re-award.
"""
from __future__ import annotations

import datetime as dt
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import DailyReview, WeeklyReview
from ..schemas import (
    DailyReviewIn,
    DailyReviewMutationOut,
    DailyReviewOut,
    WeeklyReviewIn,
    WeeklyReviewMutationOut,
    WeeklyReviewOut,
)
from ..services import xp as xp_service
from ..services.activity import run_progress_engine

router = APIRouter(prefix="/api", tags=["checkins"])


def _parse_date(value: str):
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date '{value}'")


def _week_of(review_week: str) -> tuple[int, int]:
    """Parse 'YYYY-Www' into (iso_year, iso_week)."""
    m = re.fullmatch(r"(\d{4})-W(\d{2})", review_week.strip())
    if not m:
        raise HTTPException(status_code=422, detail="Week must look like 2026-W40")
    year, week = int(m.group(1)), int(m.group(2))
    if not 1 <= week <= 53:
        raise HTTPException(status_code=422, detail="ISO week must be 1..53")
    return year, week


# --- Daily Review --------------------------------------------------------------
@router.get("/daily-reviews")
def list_daily_reviews(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(DailyReview).order_by(DailyReview.review_date.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "rows": [DailyReviewOut.model_validate(r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/daily-reviews/{review_date}", response_model=DailyReviewOut)
def get_daily_review(review_date: str, db: Session = Depends(get_db)):
    row = db.query(DailyReview).filter(
        DailyReview.review_date == _parse_date(review_date)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No daily review for this date")
    return DailyReviewOut.model_validate(row)


@router.post("/daily-reviews/{review_date}",
             response_model=DailyReviewMutationOut, status_code=201)
def create_daily_review(review_date: str, payload: DailyReviewIn,
                        db: Session = Depends(get_db)) -> DailyReviewMutationOut:
    date = _parse_date(review_date)
    if db.query(DailyReview).filter(DailyReview.review_date == date).first():
        raise HTTPException(status_code=409, detail="Daily review already exists")
    pre_total = xp_service.total_xp(db)
    row = DailyReview(review_date=date, **payload.model_dump())
    db.add(row)
    db.flush()
    awarded = xp_service.award_xp(
        db,
        event_type="daily_review",
        amount=config.XP_DAILY_REVIEW,
        idempotency_key=f"daily:{date.isoformat()}",
        entity_type="daily_review",
        entity_id=row.id,
    )
    run_progress_engine(db)
    db.commit()
    db.refresh(row)
    out = DailyReviewMutationOut.model_validate(row)
    fb = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    out.xp_awarded = fb["xp_awarded"]
    out.level_up = fb["level_up"]
    return out


@router.patch("/daily-reviews/{review_date}", response_model=DailyReviewOut)
def update_daily_review(review_date: str, payload: DailyReviewIn,
                        db: Session = Depends(get_db)):
    row = db.query(DailyReview).filter(
        DailyReview.review_date == _parse_date(review_date)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No daily review for this date")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()  # edits award ZERO XP
    db.refresh(row)
    return DailyReviewOut.model_validate(row)


# --- Weekly Review ---------------------------------------------------------------

@router.get("/weekly-reviews")
def list_weekly_reviews(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(WeeklyReview).order_by(
        WeeklyReview.iso_year.desc(), WeeklyReview.iso_week.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "rows": [WeeklyReviewOut.model_validate(r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/weekly-reviews/{review_week}", response_model=WeeklyReviewOut)
def get_weekly_review(review_week: str, db: Session = Depends(get_db)):
    year, week = _week_of(review_week)
    row = db.query(WeeklyReview).filter(
        WeeklyReview.iso_year == year, WeeklyReview.iso_week == week).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No weekly review for this week")
    return WeeklyReviewOut.model_validate(row)


@router.post("/weekly-reviews/{review_week}",
             response_model=WeeklyReviewMutationOut, status_code=201)
def create_weekly_review(review_week: str, payload: WeeklyReviewIn,
                         db: Session = Depends(get_db)) -> WeeklyReviewMutationOut:
    year, week = _week_of(review_week)
    if db.query(WeeklyReview).filter(
            WeeklyReview.iso_year == year, WeeklyReview.iso_week == week).first():
        raise HTTPException(status_code=409, detail="Weekly review already exists")
    pre_total = xp_service.total_xp(db)
    row = WeeklyReview(iso_year=year, iso_week=week, **payload.model_dump())
    db.add(row)
    db.flush()
    awarded = xp_service.award_xp(
        db,
        event_type="weekly_review",
        amount=config.XP_WEEKLY_REVIEW,
        idempotency_key=f"weekly:{year}-{week:02d}",
        entity_type="weekly_review",
        entity_id=row.id,
    )
    run_progress_engine(db)
    db.commit()
    db.refresh(row)
    out = WeeklyReviewMutationOut.model_validate(row)
    fb = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    out.xp_awarded = fb["xp_awarded"]
    out.level_up = fb["level_up"]
    return out


@router.patch("/weekly-reviews/{review_week}", response_model=WeeklyReviewOut)
def update_weekly_review(review_week: str, payload: WeeklyReviewIn,
                         db: Session = Depends(get_db)):
    year, week = _week_of(review_week)
    row = db.query(WeeklyReview).filter(
        WeeklyReview.iso_year == year, WeeklyReview.iso_week == week).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No weekly review for this week")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()  # edits award ZERO XP
    db.refresh(row)
    return WeeklyReviewOut.model_validate(row)

