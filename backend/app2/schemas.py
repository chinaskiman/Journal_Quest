"""Pydantic v2 schemas for the v2 REST API.

All input models use ``extra="forbid"`` - mass assignment of protected fields
(id, XP fields, timestamps) is impossible by construction.  Clients can never
submit XP amounts or quest rewards.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


# --- settings ----------------------------------------------------------------

class SettingCreate(StrictModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


class SettingUpdate(StrictModel):
    name: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class SettingOut(StrictModel):
    id: int
    name: str
    sort_order: int
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime


class SettingListOut(StrictModel):
    items: list[SettingOut]


# --- trades ------------------------------------------------------------------

class TradeCreate(StrictModel):
    symbol: str
    setup: str | None = None
    direction: Literal["long", "short"] | None = None
    opened_at: dt.datetime
    entry_price: float | None = None
    screenshot_path: str | None = None
    thesis: str | None = None
    notes: str | None = None
    user_pnl: float | None = None
    # a trade may be created already closed (quick capture of history)
    status: Literal["open", "closed"] = "open"
    closed_at: dt.datetime | None = None
    result: Literal["win", "loss", "breakeven"] | None = None
    result_note: str | None = None
    exit_price: float | None = None

    @field_validator("symbol", "setup")
    @classmethod
    def _label(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class TradeUpdate(StrictModel):
    symbol: str | None = None
    setup: str | None = None
    direction: Literal["long", "short"] | None = None
    opened_at: dt.datetime | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    screenshot_path: str | None = None
    thesis: str | None = None
    notes: str | None = None
    user_pnl: float | None = None
    result: Literal["win", "loss", "breakeven"] | None = None
    result_note: str | None = None
    closed_at: dt.datetime | None = None


class TradeClose(StrictModel):
    closed_at: dt.datetime | None = None
    exit_price: float | None = None
    user_pnl: float | None = None
    result: Literal["win", "loss", "breakeven"] | None = None
    result_note: str | None = None


class TradeOut(StrictModel):
    id: int
    status: str
    symbol_label: str
    setup_label: str | None
    direction: str | None
    opened_at: dt.datetime
    closed_at: dt.datetime | None
    result: str | None
    result_note: str | None
    entry_price: float | None
    exit_price: float | None
    user_pnl: float | None
    screenshot_path: str | None
    thesis: str | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class TradeListOut(StrictModel):
    rows: list[TradeOut]
    total: int
    page: int
    page_size: int


# --- reviews -------------------------------------------------------------------

class QuickReviewCreate(StrictModel):
    followed_plan: Literal["yes", "partly", "no"] | None = None
    execution_rating: int = Field(ge=1, le=5)
    went_well: str | None = None
    went_wrong: str | None = None
    improve: str | None = None


class QuickReviewUpdate(StrictModel):
    followed_plan: Literal["yes", "partly", "no"] | None = None
    execution_rating: int | None = Field(default=None, ge=1, le=5)
    went_well: str | None = None
    went_wrong: str | None = None
    improve: str | None = None


class QuickReviewOut(StrictModel):
    id: int
    trade_id: int
    followed_plan: str | None
    execution_rating: int
    went_well: str | None
    went_wrong: str | None
    improve: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class LessonIn(StrictModel):
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("lesson text must not be empty")
        return v


class DeepReviewCreate(StrictModel):
    plan_review: str | None = None
    execution_review: str | None = None
    risk_review: str | None = None
    emotions_review: str | None = None
    mistakes: str | None = None
    grade: Literal["A", "B", "C", "D", "F"] | None = None
    key_takeaway: str | None = None
    lessons: list[LessonIn] = []


class DeepReviewUpdate(StrictModel):
    plan_review: str | None = None
    execution_review: str | None = None
    risk_review: str | None = None
    emotions_review: str | None = None
    mistakes: str | None = None
    grade: Literal["A", "B", "C", "D", "F"] | None = None
    key_takeaway: str | None = None


class LessonOut(StrictModel):
    id: int
    source_type: str
    source_id: int | None
    trade_id: int | None
    text: str
    created_at: dt.datetime
    updated_at: dt.datetime


class DeepReviewOut(StrictModel):
    id: int
    trade_id: int
    plan_review: str | None
    execution_review: str | None
    risk_review: str | None
    emotions_review: str | None
    mistakes: str | None
    grade: str | None
    key_takeaway: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    lessons: list[LessonOut] = []

# --- emotional journal ----------------------------------------------------------

class EmotionalEntryCreate(StrictModel):
    emotion: str
    intensity: int = Field(ge=1, le=5)
    trade_id: int | None = None
    occurred_at: dt.datetime | None = None  # defaults to server local now
    trigger: str | None = None
    body: str | None = None

    @field_validator("emotion")
    @classmethod
    def _emotion(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("emotion must not be empty")
        return v


class EmotionalEntryUpdate(StrictModel):
    emotion: str | None = None
    intensity: int | None = Field(default=None, ge=1, le=5)
    trade_id: int | None = None
    occurred_at: dt.datetime | None = None
    trigger: str | None = None
    body: str | None = None


class EmotionalEntryOut(StrictModel):
    id: int
    trade_id: int | None
    occurred_at: dt.datetime
    local_date: dt.date
    emotion_label: str
    intensity: int
    trigger: str | None
    body: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class EmotionalListOut(StrictModel):
    rows: list[EmotionalEntryOut]
    total: int


# --- daily / weekly reviews -------------------------------------------------------

class DailyReviewIn(StrictModel):
    energy: int | None = Field(default=None, ge=1, le=5)
    focus: int | None = Field(default=None, ge=1, le=5)
    mood: int | None = Field(default=None, ge=1, le=5)
    reflection: str | None = None


class DailyReviewOut(StrictModel):
    id: int
    review_date: dt.date
    energy: int | None
    focus: int | None
    mood: int | None
    reflection: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class WeeklyReviewIn(StrictModel):
    highlights: str | None = None
    challenges: str | None = None
    patterns: str | None = None
    plan_next_week: str | None = None
    advice_to_future_me: str | None = None

    @field_validator("advice_to_future_me")
    @classmethod
    def _advice(cls, v: str | None) -> str | None:
        # empty/whitespace advice is "not written" (LQ-03 counts content only)
        if v is None:
            return v
        v = v.strip()
        return v or None


class WeeklyReviewOut(StrictModel):
    id: int
    iso_year: int
    iso_week: int
    highlights: str | None
    challenges: str | None
    patterns: str | None
    plan_next_week: str | None
    advice_to_future_me: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


# --- lessons (standalone endpoints) ------------------------------------------------

class LessonCreate(StrictModel):
    source_type: Literal["quick", "deep", "daily", "weekly", "emotional"]
    source_id: int | None = None
    trade_id: int | None = None
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("lesson text must not be empty")
        return v


class LessonUpdate(StrictModel):
    text: str


# --- gamification read models -------------------------------------------------------

class XpEventOut(StrictModel):
    id: int
    event_type: str
    amount: int
    idempotency_key: str
    entity_type: str | None
    entity_id: int | None
    awarded_at: dt.datetime


class XpSummaryOut(StrictModel):
    total_xp: int
    level: int
    title: str
    current_level_xp: int
    next_level_xp_needed: int
    next_level_total_xp: int | None
    progress_pct: float


class QuestOut(StrictModel):
    model_config = ConfigDict(extra="allow")  # service dicts carry all keys


class ClaimResultOut(StrictModel):
    awarded_xp: int
    quest: dict


class AchievementOut(StrictModel):
    model_config = ConfigDict(extra="allow")


class UiPreferenceUpdate(StrictModel):
    value: str  # JSON string; validated by the router


# --- mutation feedback (frontend integration) ------------------------------------
# Creation/claim responses include the XP the ledger actually recorded for
# that operation (0 when the idempotency key already existed) and a level-up
# payload that is only non-null when the mutation genuinely crossed a level
# threshold.  The frontend never computes XP or levels itself.

class TradeMutationOut(TradeOut):
    xp_awarded: int = 0
    level_up: dict | None = None


class QuickReviewMutationOut(QuickReviewOut):
    xp_awarded: int = 0
    level_up: dict | None = None


class DeepReviewMutationOut(DeepReviewOut):
    xp_awarded: int = 0
    level_up: dict | None = None


class LessonMutationOut(LessonOut):
    xp_awarded: int = 0
    level_up: dict | None = None


class EmotionalEntryMutationOut(EmotionalEntryOut):
    xp_awarded: int = 0
    level_up: dict | None = None


class DailyReviewMutationOut(DailyReviewOut):
    xp_awarded: int = 0
    level_up: dict | None = None


class WeeklyReviewMutationOut(WeeklyReviewOut):
    xp_awarded: int = 0
    level_up: dict | None = None


# --- streak break & recovery ---------------------------------------------------
# Habit-focused prompts only.  Nothing here asks about losses, trade size or
# trading frequency, and both fields are optional.
class StreakReflectionIn(StrictModel):
    obstacle: str | None = None
    resume_step: str | None = None

