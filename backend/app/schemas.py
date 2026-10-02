"""Pydantic schemas for the REST API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, field_validator


class TradeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    symbol: str | None = None
    opening_day: dt.date | None = None
    opening_time: dt.time | None = None
    setup_type: str | None = None
    direction: str | None = None
    volume: float | None = None
    entry_price: float | None = None
    sl_price: float | None = None
    tp_price: float | None = None
    risk: float | None = None
    bias_4h: str | None = None
    bias_1h: str | None = None
    story_behind_candles: str | None = None
    opening_rsi_condition: str | None = None
    atr: float | None = None
    mental_state: str | None = None
    why_i_entered: str | None = None
    closing_day: dt.date | None = None
    closing_time: dt.time | None = None
    closing_price: float | None = None
    closing_rsi: float | None = None
    why_i_closed: str | None = None
    commission: float | None = None
    swap: float | None = None
    note: str | None = None

    @field_validator("direction")
    @classmethod
    def _direction(cls, v: str | None) -> str | None:
        if v in (None, "", "Long", "Short"):
            return v or None
        raise ValueError("Direction must be 'Long' or 'Short'")


class TradeCreate(TradeBase):
    symbol: str


class TradeUpdate(TradeBase):
    pass


class TradeOut(TradeBase):
    id: int
    seq: int
    source_net_pnl: float | None = None
    # derived
    sl_atr_multiplier: float | None = None
    planned_rr: float | None = None
    final_rr: float | None = None
    net_pnl: float | None = None
    status: str | None = None
    duration_seconds: int | None = None
    duration_display: str | None = None
    win_streak: int = 0
    loss_streak: int = 0


class TradeListOut(BaseModel):
    rows: list[TradeOut]
    total: int
    page: int
    page_size: int


class ReorderPayload(BaseModel):
    ordered_ids: list[int]


class OptionCreate(BaseModel):
    value: str


class OptionUpdate(BaseModel):
    value: str


class OptionReorderPayload(BaseModel):
    ordered_ids: list[int]


class OptionOut(BaseModel):
    id: int
    list_key: str
    value: str
    position: int


class OptionsOut(BaseModel):
    lists: dict[str, list[OptionOut]]


class ImportReportOut(BaseModel):
    trades_imported: int
    options_imported: int
    mode: str
    workbook: str
