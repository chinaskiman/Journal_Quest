"""Level progression - derived purely from persisted XP.

Levels measure journaling and reflection habit only.  Thresholds follow the
approved formula: XP to advance from level n to n+1 = 100 + 50 * (n - 1),
giving cumulative thresholds 0, 100, 250, 450, 700, 1000, 1350, ...
No bonus XP is granted for reaching a level.
"""
from __future__ import annotations

from dataclasses import dataclass

# Approved title mapping for levels 1-14 plus a mastery tier for 15+.
LEVEL_TITLES: dict[int, str] = {
    1: "Drifter",
    2: "Signal Listener",
    3: "Log Keeper",
    4: "Deck Observer",
    5: "Flight Cadet",
    6: "Junior Analyst",
    7: "Chronologist",
    8: "Mirror Navigator",
    9: "Pattern Seeker",
    10: "Cartographer of Habits",
    11: "Archivist of Self",
    12: "Mission Specialist",
    13: "Sector Commander",
    14: "Quest Master",
}
MASTERY_TITLE = "Legend of the Quest"


def xp_to_next(level: int) -> int:
    """XP required to advance FROM ``level`` TO ``level + 1``."""
    if level < 1:
        raise ValueError("level must be >= 1")
    return 100 + 50 * (level - 1)


def cumulative_threshold(level: int) -> int:
    """Total XP required to REACH ``level`` (level 1 = 0)."""
    if level < 1:
        raise ValueError("level must be >= 1")
    return sum(xp_to_next(n) for n in range(1, level))


# Precomputed thresholds: level -> cumulative XP.
_THRESHOLDS = {1: 0}
_MAX_PRECOMPUTED = 100  # far beyond any realistic XP total
_running = 0
for _n in range(1, _MAX_PRECOMPUTED):
    _running += xp_to_next(_n)
    _THRESHOLDS[_n + 1] = _running


def title_for_level(level: int) -> str:
    return LEVEL_TITLES.get(level, MASTERY_TITLE)


@dataclass(frozen=True)
class LevelInfo:
    level: int
    title: str
    total_xp: int
    current_level_xp: int          # XP earned within the current level
    next_level_xp_needed: int     # XP still needed to reach the next level
    next_level_total_xp: int | None  # cumulative threshold of the next level
    progress_pct: float            # 0..100 within the current level


def level_info(total_xp: int) -> LevelInfo:
    """Deterministically derive the level from a persisted XP total."""
    if total_xp < 0:
        total_xp = 0
    level = 1
    for lvl in sorted(_THRESHOLDS):
        if total_xp >= _THRESHOLDS[lvl]:
            level = lvl
    level = max(level, 1)
    base = _THRESHOLDS[level]
    in_level = total_xp - base
    need = xp_to_next(level)
    next_total = base + need
    return LevelInfo(
        level=level,
        title=title_for_level(level),
        total_xp=total_xp,
        current_level_xp=in_level,
        next_level_xp_needed=max(0, next_total - total_xp),
        next_level_total_xp=next_total,
        progress_pct=round(min(100.0, in_level / need * 100.0), 2) if need else 100.0,
    )


def level_from_xp(total_xp: int) -> int:
    return level_info(total_xp).level
