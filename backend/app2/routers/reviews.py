"""Reflection endpoints: Quick Review, Deep Review, Lessons.

XP rules:
* Quick Review create: +15, key ``qreview:{review_id}`` (one per review).
* Deep Review create: +30, key ``dreview:{review_id}``.
* Lesson: +10 each, max 3 per parent review, key ``lesson:{lesson_id}``;
  lessons beyond the cap are stored but earn no XP.  Edits/retries never
  re-award.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import DeepReview, Lesson, QuickReview, Trade, XpEvent
from ..schemas import (
    DeepReviewCreate,
    DeepReviewMutationOut,
    DeepReviewOut,
    DeepReviewUpdate,
    LessonCreate,
    LessonMutationOut,
    LessonOut,
    LessonUpdate,
    QuickReviewCreate,
    QuickReviewMutationOut,
    QuickReviewOut,
    QuickReviewUpdate,
)
from ..services import xp as xp_service
from ..services.activity import run_progress_engine

router = APIRouter(prefix="/api", tags=["reviews"])


def _get_trade(db: Session, trade_id: int) -> Trade:
    trade = db.get(Trade, trade_id)
    if trade is None or trade.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


def _lessons_for(db: Session, source_type: str, source_id: int) -> list[Lesson]:
    return (
        db.query(Lesson)
        .filter(Lesson.source_type == source_type, Lesson.source_id == source_id)
        .order_by(Lesson.id)
        .all()
    )


def _lessons_earned_for(db: Session, source_type: str, source_id: int) -> int:
    """Count lesson-XP events already awarded for one parent review."""
    lessons = _lessons_for(db, source_type, source_id)
    if not lessons:
        return 0
    keys = [f"lesson:{l.id}" for l in lessons]
    return db.query(XpEvent).filter(XpEvent.idempotency_key.in_(keys)).count()


def _award_lesson(db: Session, lesson: Lesson) -> int:
    """Award +10 XP if this parent review still has lesson-XP budget."""
    if lesson.source_id is None:
        return 0
    earned = _lessons_earned_for(db, lesson.source_type, lesson.source_id)
    if earned >= config.XP_LESSON_CAP_PER_REVIEW:
        return 0  # saved, but beyond the cap - no XP
    return xp_service.award_xp(
        db,
        event_type="lesson",
        amount=config.XP_LESSON,
        idempotency_key=f"lesson:{lesson.id}",
        entity_type="lesson",
        entity_id=lesson.id,
    )


# --- Quick Review --------------------------------------------------------------

@router.get("/trades/{trade_id}/quick-review", response_model=QuickReviewOut)
def get_quick_review(trade_id: int, db: Session = Depends(get_db)):
    _get_trade(db, trade_id)
    row = db.query(QuickReview).filter(QuickReview.trade_id == trade_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No quick review for this trade")
    return QuickReviewOut.model_validate(row)


@router.post("/trades/{trade_id}/quick-review",
             response_model=QuickReviewMutationOut, status_code=201)
def create_quick_review(trade_id: int, payload: QuickReviewCreate,
                        db: Session = Depends(get_db)) -> QuickReviewMutationOut:
    _get_trade(db, trade_id)
    if db.query(QuickReview).filter(QuickReview.trade_id == trade_id).first():
        raise HTTPException(status_code=409, detail="Quick review already exists")
    pre_total = xp_service.total_xp(db)
    row = QuickReview(trade_id=trade_id, **payload.model_dump())
    db.add(row)
    db.flush()
    awarded = xp_service.award_xp(
        db,
        event_type="quick_review",
        amount=config.XP_QUICK_REVIEW,
        idempotency_key=f"qreview:{row.id}",
        entity_type="quick_review",
        entity_id=row.id,
    )
    run_progress_engine(db)
    db.commit()
    db.refresh(row)
    out = QuickReviewMutationOut.model_validate(row)
    fb = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    out.xp_awarded = fb["xp_awarded"]
    out.level_up = fb["level_up"]
    return out


@router.patch("/quick-reviews/{review_id}", response_model=QuickReviewOut)
def update_quick_review(review_id: int, payload: QuickReviewUpdate,
                        db: Session = Depends(get_db)):
    row = db.get(QuickReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Quick review not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()  # edits award ZERO XP - ledger untouched
    db.refresh(row)
    return QuickReviewOut.model_validate(row)

@router.delete("/quick-reviews/{review_id}", status_code=204)
def delete_quick_review(review_id: int, db: Session = Depends(get_db)):
    row = db.get(QuickReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Quick review not found")
    db.delete(row)
    db.commit()  # no XP clawback - ledger is append-only
    return None


# --- Deep Review ----------------------------------------------------------------

def _deep_review_out(db: Session, row: DeepReview,
                     out_cls: type = DeepReviewOut) -> DeepReviewOut:
    lessons = _lessons_for(db, "deep", row.id)
    return out_cls(
        **{c: getattr(row, c) for c in (
            "id", "trade_id", "plan_review", "execution_review", "risk_review",
            "emotions_review", "mistakes", "grade", "key_takeaway",
            "created_at", "updated_at")},
        lessons=[LessonOut.model_validate(l) for l in lessons],
    )


@router.get("/trades/{trade_id}/deep-review", response_model=DeepReviewOut)
def get_deep_review(trade_id: int, db: Session = Depends(get_db)):
    _get_trade(db, trade_id)
    row = db.query(DeepReview).filter(DeepReview.trade_id == trade_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No deep review for this trade")
    return _deep_review_out(db, row)


@router.post("/trades/{trade_id}/deep-review",
             response_model=DeepReviewMutationOut, status_code=201)
def create_deep_review(trade_id: int, payload: DeepReviewCreate,
                       db: Session = Depends(get_db)) -> DeepReviewMutationOut:
    _get_trade(db, trade_id)
    if db.query(DeepReview).filter(DeepReview.trade_id == trade_id).first():
        raise HTTPException(status_code=409, detail="Deep review already exists")
    pre_total = xp_service.total_xp(db)
    row = DeepReview(
        trade_id=trade_id,
        plan_review=payload.plan_review,
        execution_review=payload.execution_review,
        risk_review=payload.risk_review,
        emotions_review=payload.emotions_review,
        mistakes=payload.mistakes,
        grade=payload.grade,
        key_takeaway=payload.key_takeaway,
    )
    db.add(row)
    db.flush()
    awarded = xp_service.award_xp(
        db,
        event_type="deep_review",
        amount=config.XP_DEEP_REVIEW,
        idempotency_key=f"dreview:{row.id}",
        entity_type="deep_review",
        entity_id=row.id,
    )
    for lesson_in in payload.lessons:
        lesson = Lesson(
            source_type="deep", source_id=row.id, trade_id=trade_id,
            text=lesson_in.text,
        )
        db.add(lesson)
        db.flush()
        awarded += _award_lesson(db, lesson)  # capped at 3 per review
    run_progress_engine(db)
    db.commit()
    db.refresh(row)
    out = _deep_review_out(db, row, DeepReviewMutationOut)
    fb = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    out.xp_awarded = fb["xp_awarded"]
    out.level_up = fb["level_up"]
    return out


@router.patch("/deep-reviews/{review_id}", response_model=DeepReviewOut)
def update_deep_review(review_id: int, payload: DeepReviewUpdate,
                       db: Session = Depends(get_db)):
    row = db.get(DeepReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Deep review not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()  # edits award ZERO XP
    db.refresh(row)
    return _deep_review_out(db, row)


@router.delete("/deep-reviews/{review_id}", status_code=204)
def delete_deep_review(review_id: int, db: Session = Depends(get_db)):
    row = db.get(DeepReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Deep review not found")
    db.delete(row)
    db.commit()  # no XP clawback
    return None


# --- Lessons (standalone) ---------------------------------------------------------

@router.get("/lessons")
def list_lessons(
    source_type: str | None = None,
    trade_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Lesson)
    if source_type:
        q = q.filter(Lesson.source_type == source_type)
    if trade_id is not None:
        q = q.filter(Lesson.trade_id == trade_id)
    total = q.count()
    rows = q.order_by(Lesson.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "rows": [LessonOut.model_validate(r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/lessons", response_model=LessonMutationOut, status_code=201)
def create_lesson(payload: LessonCreate,
                  db: Session = Depends(get_db)) -> LessonMutationOut:
    if payload.trade_id is not None:
        _get_trade(db, payload.trade_id)
    if payload.source_type in ("quick", "deep") and payload.source_id is None:
        raise HTTPException(
            status_code=422,
            detail="source_id is required for quick/deep review lessons",
        )
    pre_total = xp_service.total_xp(db)
    lesson = Lesson(
        source_type=payload.source_type,
        source_id=payload.source_id,
        trade_id=payload.trade_id,
        text=payload.text,
    )
    db.add(lesson)
    db.flush()
    awarded = _award_lesson(db, lesson)  # respects the 3-per-parent-review cap
    run_progress_engine(db)
    db.commit()
    db.refresh(lesson)
    out = LessonMutationOut.model_validate(lesson)
    fb = xp_service.mutation_feedback(
        db, pre_total_xp=pre_total, xp_awarded=awarded)
    out.xp_awarded = fb["xp_awarded"]
    out.level_up = fb["level_up"]
    return out


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
def update_lesson(lesson_id: int, payload: LessonUpdate,
                  db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    lesson.text = payload.text.strip() or lesson.text
    db.commit()  # edits award ZERO XP
    db.refresh(lesson)
    return LessonOut.model_validate(lesson)


@router.delete("/lessons/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: int, db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    db.delete(lesson)
    db.commit()  # no XP clawback
    return None

