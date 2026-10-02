"""Level thresholds, boundaries and progression derivation."""
from __future__ import annotations

import pytest

from app2.services.levels import (
    cumulative_threshold,
    level_from_xp,
    level_info,
    title_for_level,
    xp_to_next,
)

APPROVED = {1: 0, 2: 100, 3: 250, 4: 450, 5: 700, 6: 1000, 7: 1350,
            8: 1750, 9: 2200, 10: 2700}


def test_approved_cumulative_thresholds():
    for lvl, xp in APPROVED.items():
        assert cumulative_threshold(lvl) == xp, f"level {lvl}"


def test_formula_continues_beyond_10():
    # 100 + 50*(n-1) steps: L10->11 needs 550, 11->12 needs 600
    assert xp_to_next(10) == 550
    assert cumulative_threshold(11) == 2700 + 550
    assert cumulative_threshold(12) == 3250 + 600


@pytest.mark.parametrize("xp,expected", [
    (0, 1), (99, 1), (100, 2), (101, 2), (249, 2), (250, 3),
    (449, 3), (450, 4), (699, 4), (700, 5), (999, 5), (1000, 6),
    (1349, 6), (1350, 7), (1749, 7), (1750, 8), (2199, 8), (2200, 9),
    (2699, 9), (2700, 10), (3249, 10), (3250, 11), (100000, 62),
])
def test_exact_boundaries(xp, expected):
    assert level_from_xp(xp) == expected


def test_progress_to_next_level():
    info = level_info(120)  # level 2 (base 100), needs 150 to reach 3
    assert info.level == 2
    assert info.current_level_xp == 20
    assert info.next_level_xp_needed == 130
    assert info.next_level_total_xp == 250
    assert info.progress_pct == pytest.approx(20 / 150 * 100, abs=0.01)


def test_mid_level_fields_match_approved_thresholds():
    # 492 XP is exactly the state shown in the Phase 3 screenshots: level 4
    # (base 450) with 42 XP inside the level and 208 XP left to level 5.
    # The UI once displayed 166 because it subtracted current_level_xp from
    # next_level_xp_needed - these fields pin the correct contract.
    info = level_info(492)
    assert info.level == 4
    assert info.title == "Deck Observer"
    assert info.current_level_xp == 42
    assert info.next_level_xp_needed == 208
    assert info.next_level_total_xp == 700
    assert info.progress_pct == pytest.approx(42 / 250 * 100, abs=0.01)  # 16.8


@pytest.mark.parametrize("total", [0, 30, 99, 100, 120, 492, 699, 700, 1000,
                                   1350, 2700, 5000, 100000])
def test_next_level_xp_needed_is_remaining_not_level_span(total):
    """`next_level_xp_needed` is what is LEFT, never the level's total span.

    This is the invariant the frontend violated.  Note the two values only
    coincide at the very start of a level, which is why a 0-XP fixture or an
    exact threshold total could never expose the bug.
    """
    info = level_info(total)
    span = xp_to_next(info.level)
    assert info.current_level_xp + info.next_level_xp_needed == span
    assert info.next_level_xp_needed == span - info.current_level_xp
    assert info.next_level_total_xp == cumulative_threshold(info.level) + span
    # progress_pct is defined from the level span and in-level XP only.
    assert info.progress_pct == pytest.approx(
        min(100.0, info.current_level_xp / span * 100.0), abs=0.01)


def test_progress_pct_is_monotonic_within_a_level():
    previous = -1.0
    for total in range(450, 700, 10):  # level 4: base 450, span 250
        info = level_info(total)
        assert info.level == 4
        assert info.progress_pct >= previous
        previous = info.progress_pct
    assert previous == pytest.approx(240 / 250 * 100, abs=0.5)


def test_titles_mapping():
    assert title_for_level(1) == "Drifter"
    assert title_for_level(10) == "Cartographer of Habits"
    assert title_for_level(15) == "Legend of the Quest"
    assert title_for_level(99) == "Legend of the Quest"


def test_level_derived_from_persisted_ledger(client):
    from tests_v2.conftest import make_trade, seed_settings
    seed_settings(client)
    # 4 trades = 80 XP -> level 1; +1 trade = 100 -> level 2 boundary
    for _ in range(4):
        make_trade(client)
    assert client.get("/api/xp").json()["level"] == 1
    make_trade(client)
    summary = client.get("/api/xp").json()
    assert summary["total_xp"] == 100
    assert summary["level"] == 2
    assert summary["next_level_xp_needed"] == 150


def test_no_level_dependence_on_pnl(client):
    from tests_v2.conftest import make_trade, seed_settings
    seed_settings(client)
    make_trade(client, user_pnl=1_000_000)   # huge manual P&L
    make_trade(client, user_pnl=-1_000_000)
    assert client.get("/api/xp").json()["total_xp"] == 40  # 2 x +20 only
