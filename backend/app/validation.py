"""Categorical validation that mirrors the workbook's dropdown behaviour.

Invalid categorical values are rejected with HTTP 422 unless the user adds
the value through the Options page first.  Two deliberate exceptions:

* the Excel importer bypasses this module so existing values are preserved
  verbatim (e.g. ``XCUUSD``, setup type ``welcome``);
* when *editing* an existing trade, RSI condition lines that are already
  stored on that trade may be kept even if they are not in the Options
  list (the imported journal contains hand-typed variants such as
  ``Rising From Support`` vs the option ``Rising from Support``).
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import OptionValue, Trade

OPTION_LIST_KEYS = ("symbol", "setup_type", "bias", "rsi_condition", "mental_state")

_FIELD_TO_LIST = {
    "symbol": "symbol",
    "setup_type": "setup_type",
    "bias_4h": "bias",
    "bias_1h": "bias",
    "mental_state": "mental_state",
}


def _option_sets(db: Session) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {key: set() for key in OPTION_LIST_KEYS}
    for row in db.query(OptionValue.list_key, OptionValue.value).all():
        if row.list_key in sets:
            sets[row.list_key].add(row.value)
    return sets


def validate_trade_payload(
    db: Session, payload: dict, current: Trade | None
) -> None:
    lists = _option_sets(db)
    errors: list[str] = []

    for field, list_key in _FIELD_TO_LIST.items():
        if field in payload:
            value = payload.get(field)
            if value not in (None, "") and value not in lists[list_key]:
                errors.append(
                    f"{field} '{value}' is not in the Options '{list_key}' list"
                )

    if "opening_rsi_condition" in payload:
        value = payload.get("opening_rsi_condition")
        if value:
            allowed = set(lists["rsi_condition"])
            if current is not None and current.opening_rsi_condition:
                allowed |= {
                    line
                    for line in current.opening_rsi_condition.split("\n")
                    if line.strip()
                }
            for line in value.split("\n"):
                if line.strip() and line not in allowed:
                    errors.append(
                        f"RSI condition '{line}' is not in the Options list"
                    )

    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
