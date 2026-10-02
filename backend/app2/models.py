"""Trade Quest v2 - database models.

Schema follows PHASE1_BLUEPRINT.md §H.  Key invariants:

* Trade results (win/loss/breakeven) are ALWAYS entered manually - the app
  never computes a result from prices, direction or any other field.
* Journal records store *label snapshots* (symbol_label, setup_label,
  emotion_label) so renaming/disabling/deleting a settings item never changes
  the meaning of historical records.
* ``xp_events`` is an append-only ledger; the UNIQUE idempotency key is the
  hard duplicate-XP firewall.
* No XP is ever awarded for P&L, trade closure, edits or deletions.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


# --- settings lists (identical shape) ---------------------------------------

class Setting(TimestampMixin, Base):
    __abstract__ = True
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)


class Symbol(Setting):
    __tablename__ = "symbols"
    __table_args__ = (UniqueConstraint("name", name="uq_symbols_name"),)


class Setup(Setting):
    __tablename__ = "setups"
    __table_args__ = (UniqueConstraint("name", name="uq_setups_name"),)


class Emotion(Setting):
    __tablename__ = "emotions"
    __table_args__ = (UniqueConstraint("name", name="uq_emotions_name"),)


# --- trades -----------------------------------------------------------------

class Trade(TimestampMixin, Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(16), CheckConstraint("status IN ('open','closed')",
                                    name="ck_trades_status"),
        nullable=False, default="open",
    )
    # label snapshots - never FKs, history is immune to settings changes
    symbol_label: Mapped[str] = mapped_column(String(128), nullable=False)
    setup_label: Mapped[str | None] = mapped_column(String(128))
    direction: Mapped[str | None] = mapped_column(
        String(8), CheckConstraint("direction IN ('long','short')",
                                   name="ck_trades_direction")
    )
    opened_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    # manual result - the ONLY source of this value is the user
    result: Mapped[str | None] = mapped_column(
        String(16),
        CheckConstraint("result IN ('win','loss','breakeven')", name="ck_trades_result"),
    )
    result_note: Mapped[str | None] = mapped_column(Text)
    entry_price: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    # manually entered P&L - never computed, never affects progression
    user_pnl: Mapped[float | None] = mapped_column(Float)
    # user supplied file path only - image bytes are never stored
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    thesis: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    quick_review: Mapped["QuickReview | None"] = relationship(
        back_populates="trade", uselist=False, cascade="all, delete-orphan"
    )
    deep_review: Mapped["DeepReview | None"] = relationship(
        back_populates="trade", uselist=False, cascade="all, delete-orphan"
    )
    emotional_entries: Mapped[list["EmotionalEntry"]] = relationship(
        back_populates="trade"
    )

    __table_args__ = (
        Index("ix_trades_status", "status"),
        Index("ix_trades_opened_at", "opened_at"),
        Index("ix_trades_symbol_label", "symbol_label"),
    )

# --- reviews -----------------------------------------------------------------

class QuickReview(TimestampMixin, Base):
    __tablename__ = "quick_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    followed_plan: Mapped[str | None] = mapped_column(
        String(16),
        CheckConstraint(
            "followed_plan IN ('yes','partly','no')", name="ck_qr_followed_plan"
        ),
    )
    execution_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    went_well: Mapped[str | None] = mapped_column(Text)
    went_wrong: Mapped[str | None] = mapped_column(Text)
    improve: Mapped[str | None] = mapped_column(Text)

    trade: Mapped[Trade] = relationship(back_populates="quick_review")

    __table_args__ = (
        CheckConstraint("execution_rating BETWEEN 1 AND 5", name="ck_qr_rating"),
    )


class DeepReview(TimestampMixin, Base):
    __tablename__ = "deep_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int] = mapped_column(
        ForeignKey("trades.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan_review: Mapped[str | None] = mapped_column(Text)
    execution_review: Mapped[str | None] = mapped_column(Text)
    risk_review: Mapped[str | None] = mapped_column(Text)
    emotions_review: Mapped[str | None] = mapped_column(Text)
    mistakes: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(
        String(1), CheckConstraint("grade IN ('A','B','C','D','F')", name="ck_dr_grade")
    )
    key_takeaway: Mapped[str | None] = mapped_column(Text)

    trade: Mapped[Trade] = relationship(back_populates="deep_review")


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(
        String(16),
        CheckConstraint(
            "source_type IN ('quick','deep','daily','weekly','emotional')",
            name="ck_lessons_source",
        ),
    )
    source_id: Mapped[int | None] = mapped_column(Integer)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_lessons_source", "source_type", "source_id"),
        Index("ix_lessons_trade", "trade_id"),
    )


class EmotionalEntry(TimestampMixin, Base):
    __tablename__ = "emotional_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id", ondelete="SET NULL"))
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    # local calendar date used for XP grouping (denormalized from occurred_at
    # in the server's local timezone at creation time)
    local_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    emotion_label: Mapped[str] = mapped_column(String(128), nullable=False)
    intensity: Mapped[int] = mapped_column(
        Integer, CheckConstraint("intensity BETWEEN 1 AND 5", name="ck_ee_intensity")
    )
    trigger: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)

    trade: Mapped[Trade | None] = relationship(back_populates="emotional_entries")

    __table_args__ = (
        Index("ix_emotional_local_date", "local_date"),
        Index("ix_emotional_trade", "trade_id"),
    )


class DailyReview(TimestampMixin, Base):
    __tablename__ = "daily_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_date: Mapped[dt.date] = mapped_column(Date, nullable=False, unique=True)
    energy: Mapped[int | None] = mapped_column(
        Integer, CheckConstraint("energy BETWEEN 1 AND 5", name="ck_dv_energy")
    )
    focus: Mapped[int | None] = mapped_column(
        Integer, CheckConstraint("focus BETWEEN 1 AND 5", name="ck_dv_focus")
    )
    mood: Mapped[int | None] = mapped_column(
        Integer, CheckConstraint("mood BETWEEN 1 AND 5", name="ck_dv_mood")
    )
    reflection: Mapped[str | None] = mapped_column(Text)


class WeeklyReview(TimestampMixin, Base):
    __tablename__ = "weekly_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iso_year: Mapped[int] = mapped_column(Integer, nullable=False)
    iso_week: Mapped[int] = mapped_column(Integer, nullable=False)
    highlights: Mapped[str | None] = mapped_column(Text)
    challenges: Mapped[str | None] = mapped_column(Text)
    patterns: Mapped[str | None] = mapped_column(Text)
    plan_next_week: Mapped[str | None] = mapped_column(Text)
    # Blueprint quest LQ-03 "Mentor Voice": advice-to-future-me written in
    # 4 Weekly Reviews.  Nullable so historical reviews stay valid without
    # inventing content; only non-empty values count for the quest.
    advice_to_future_me: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("iso_year", "iso_week", name="uq_weekly_reviews_year_week"),
        CheckConstraint("iso_week BETWEEN 1 AND 53", name="ck_wr_week"),
    )

# --- gamification -------------------------------------------------------------

class XpEvent(Base):
    """Append-only XP ledger.  NEVER updated or deleted by normal operations."""

    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)  # audit metadata (JSON)
    awarded_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_xp_events_awarded_at", "awarded_at"),)


class QuestProgress(TimestampMixin, Base):
    __tablename__ = "quest_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quest_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    # claim state (explicit claim workflow): a completed quest awards XP only
    # after a successful, idempotent claim.
    claimed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class AchievementUnlock(Base):
    """Immutable unlock history - rows are never removed once written."""

    __tablename__ = "achievement_unlocks"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    unlocked_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class UiPreference(Base):
    __tablename__ = "ui_preferences"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(512))


# --- streak break & recovery ---------------------------------------------------
# Both tables are additive: ``create_all`` creates them for new databases and for
# already-existing v2 databases, and never rewrites historical rows.  No existing
# table is altered by this feature.


class StreakEvent(Base):
    """One qualifying journaling-streak break, and its recovery lifecycle.

    Identity / idempotency
    ----------------------
    ``broke_on``      - the last active local day of the run that ended.  Each
                        run ends on exactly one active day, so this uniquely
                        identifies a break and stops the *same* historical gap
                        from being processed again on a later day.
    ``detected_on``   - the local day the break surfaced (today and yesterday
                        both inactive).  Unique, so repeated evaluation on the
                        same day cannot create a second event.

    Both carry database-level UNIQUE constraints: application-level checks alone
    would not be concurrency-safe.
    """

    __tablename__ = "streak_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broke_on: Mapped[dt.date] = mapped_column(Date, nullable=False, unique=True)
    detected_on: Mapped[dt.date] = mapped_column(Date, nullable=False, unique=True)
    streak_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detected_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # recovery lifecycle: detected -> reflection_done -> recovery_done
    reflection_done_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    recovery_target: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    recovery_done_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    alert_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_streak_events_detected_on", "detected_on"),
    )


class StreakQuestClaim(Base):
    """One RC-01 / RC-02 reward claim, scoped to ONE streak-break event.

    RC quests are the only per-event quests: each independent break can earn the
    reward again.  Two database-level UNIQUE constraints make that safe under
    concurrency and retries:

    * ``(event_id, quest_code)`` - the same event+quest can never be claimed
      twice, even from two simultaneous requests.
    * ``idempotency_key``         - ``streak:{event_id}:{quest_code}`` mirrors the
      XP ledger's own unique key, so the ledger itself is the second firewall.
    """

    __tablename__ = "streak_quest_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("streak_events.id", ondelete="CASCADE"), nullable=False
    )
    quest_code: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    claimed_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("event_id", "quest_code", name="uq_streak_claim_event_quest"),
        Index("ix_streak_claim_quest_code", "quest_code"),
    )


class StreakReflection(Base):
    """Optional, non-judgmental reflection for exactly one streak event.

    ``event_id`` is UNIQUE: one reflection per event.  Re-saving updates the
    existing row, so a client cannot create duplicates or re-trigger a reward.
    """

    __tablename__ = "streak_reflections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("streak_events.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    # Habit-focused prompts only - never losses, trade size or trading frequency.
    obstacle: Mapped[str | None] = mapped_column(Text)
    resume_step: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


