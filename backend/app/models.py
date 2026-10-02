"""Database models.

The ``trades`` table reproduces the 34 columns of the Journal sheet of the
source workbook.  Only *input* columns are persisted - every calculated
column (SL ATR Multiplier, R:R, Final R:R, Net PnL, Status, Duration and the
streak helpers) is derived on the fly by :mod:`app.calculations`, mirroring
the live formulas of the spreadsheet.

Excel column letters are noted per field for traceability.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # A - '#' (journal row order; drives the streak helpers)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # --- input columns -----------------------------------------------------
    symbol: Mapped[str | None] = mapped_column(String(32))              # B
    opening_day: Mapped[dt.date | None] = mapped_column(Date)           # C
    opening_time: Mapped[dt.time | None] = mapped_column(Time)          # D
    setup_type: Mapped[str | None] = mapped_column(String(64))          # E
    direction: Mapped[str | None] = mapped_column(String(8))            # F
    volume: Mapped[float | None] = mapped_column(Float)                 # G
    entry_price: Mapped[float | None] = mapped_column(Float)            # H
    sl_price: Mapped[float | None] = mapped_column(Float)              # I
    tp_price: Mapped[float | None] = mapped_column(Float)               # K
    risk: Mapped[float | None] = mapped_column(Float)                   # M
    bias_4h: Mapped[str | None] = mapped_column(String(32))             # N
    bias_1h: Mapped[str | None] = mapped_column(String(32))             # O
    story_behind_candles: Mapped[str | None] = mapped_column(Text)       # P
    opening_rsi_condition: Mapped[str | None] = mapped_column(Text)      # Q (multi line)
    atr: Mapped[float | None] = mapped_column(Float)                   # R
    mental_state: Mapped[str | None] = mapped_column(String(32))         # S
    why_i_entered: Mapped[str | None] = mapped_column(Text)             # T
    closing_day: Mapped[dt.date | None] = mapped_column(Date)           # U
    closing_time: Mapped[dt.time | None] = mapped_column(Time)         # V
    closing_price: Mapped[float | None] = mapped_column(Float)         # W
    closing_rsi: Mapped[float | None] = mapped_column(Float)           # X
    why_i_closed: Mapped[str | None] = mapped_column(Text)              # Y
    commission: Mapped[float | None] = mapped_column(Float)            # AA
    swap: Mapped[float | None] = mapped_column(Float)                   # AB
    note: Mapped[str | None] = mapped_column(Text)                      # AF

    # --- audit / meta -------------------------------------------------------
    # Literal value found in the workbook's hardcoded AC column.  Read-only
    # reference; the app never uses it for calculations.
    source_net_pnl: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("seq", name="uq_trades_seq"),
        Index("ix_trades_symbol", "symbol"),
        Index("ix_trades_direction", "direction"),
        Index("ix_trades_setup_type", "setup_type"),
        Index("ix_trades_mental_state", "mental_state"),
        Index("ix_trades_opening_day", "opening_day"),
        Index("ix_trades_closing_day", "closing_day"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Trade #{self.seq} {self.symbol} {self.direction}>"


class OptionValue(Base):
    """One row of the Options sheet (dropdown source lists)."""

    __tablename__ = "option_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_key: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("list_key", "value", name="uq_option_value"),
        Index("ix_option_list_key", "list_key"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OptionValue {self.list_key}:{self.value!r}>"


class AppState(Base):
    """Small key/value store (import flags etc.)."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(String(512))
