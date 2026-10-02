"""Shared write-path helper.

Every XP-awarding router follows the same transactional pattern:

1. validate the payload,
2. persist the activity,
3. award the XP event with a unique idempotency key (same transaction),
4. re-evaluate quests + achievements,
5. commit - or roll back entirely on any failure.

This module centralizes step 4/5 so no router forgets it.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from . import achievements as achievements_service
from . import quests as quests_service
from . import streaks as streaks_service


def run_progress_engine(db: Session) -> None:
    """Re-evaluate quests and achievements from persisted records.

    Streak detection runs FIRST so RC-01/RC-02 and the recovery achievement see
    a freshly persisted break event in the same transaction.  Detection is
    idempotent, so calling this on every request is safe.
    """
    streaks_service.evaluate(db)
    quests_service.evaluate_quests(db)
    achievements_service.evaluate_achievements(db)
