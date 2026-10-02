# Trade Quest — Phase 2 Implementation Report

Date: 2026-10-01 · Status: **Complete — awaiting user approval before Phase 3**

## 1. Summary of what was implemented

The complete Phase 2 backend foundation for the gamified Trade Quest journal,
built as a new self-contained package `backend/app2/` (FastAPI + SQLAlchemy 2 +
SQLite + Pydantic v2): 15-table data model, settings CRUD with historical-label
preservation, trade journal + Quick Capture with manual close and optional
manual P&L, Quick/Deep Reviews + Lessons, Emotional Journal, Daily/Weekly
Reviews, append-only XP ledger with unique idempotency keys, level engine,
23-quest catalog with explicit claim workflow, 13 achievements, dashboard
aggregation, local backup endpoint, Windows launch scripts, docs, and a
100-test suite. **Architectural deviation (documented):** v2 lives in
`backend/app2` with its own fresh DB `data/tradequest_v2.db` instead of
replacing `backend/app` in place — this guarantees the old app, old database,
old tests and current frontend remain a verified rollback path. Phase 3 will
promote app2 to the primary app.

## 2. Database tables & relationships

15 tables (see PHASE1_BLUEPRINT.md Appendix P.2): `symbols`, `setups`,
`emotions` (soft-archival settings lists); `trades` (label-snapshot fields —
no FK to settings, so history is immune to renames/deletes; soft delete);
`quick_reviews`/`deep_reviews` (1:1 → trades, unique trade_id, cascade);
`lessons` (polymorphic source_type/source_id + optional trade_id);
`emotional_entries` (optional trade FK SET NULL, denormalized local_date);
`daily_reviews` (unique date); `weekly_reviews` (unique iso_year+iso_week);
`xp_events` (append-only, UNIQUE idempotency_key); `quest_progress`
(unique quest_code, completed_at + **claimed_at** added for the claim
workflow); `achievement_unlocks` (code PK, immutable); `ui_preferences`;
`app_meta`. Change vs. Phase 1 sketch: added `claimed_at` to quest_progress.

## 3. API endpoints added

~45 endpoints (full list: PHASE1_BLUEPRINT.md §P.8). Nothing in the v1 API
was changed or removed; v2 serves on port 8001 under the same `/api` prefix
in a separate process.

## 4. XP & idempotency implementation

All awards flow through `services/xp.py:award_xp()` inside the caller's
transaction (persist activity → flush → insert ledger event → single commit).
Keys: `capture:{trade_id}`, `qreview:{id}`, `dreview:{id}`, `lesson:{id}`,
`emotional:{local_date}`, `emotional-entry:{entry_id}`, `daily:{date}`,
`weekly:{year-week}`, `quest:{catalog_version}:{code}`. The UNIQUE
constraint is the concurrency backstop; a pre-existing key yields 0 XP.
Total XP is always summed from the ledger; no client XP input exists
(`extra="forbid"` schemas reject any injected field — tested). Edits,
deletes, close and P&L changes insert nothing (no clawback).

## 5. Quest completion & claim workflow

Evaluation recomputes progress from persisted counts on every write and on
`GET /api/quests` (latched completion). Marking complete awards nothing.
`POST /api/quests/{code}/claim` validates active ∧ completed ∧ unclaimed ∧
reward-decided, then inserts the quest ledger event and sets `claimed_at`
atomically. Incomplete → 409; duplicate/concurrent → 409 with no double
award (tested); claim state persists across restart (tested).

## 6. Consistency Quest status

CN-01/02/03 are implemented, **opt-in and disabled by default**
(enabled via `PUT /api/preferences/consistency_quests_enabled` with
`{"value": "true"}`). Their reward XP values remain **UNDECIDED**
(`reward_xp = null`): they can reach "completed" but are **not claimable**
until the user chooses values — claiming returns 409 "undecided". The reward
is a single catalog constant per quest; defining values later requires no
schema or ledger redesign. **This is the main decision still pending from the
user.**

## 7. Emotional Journal XP behavior

Exact approved rule implemented: first entry per **server-local calendar day**
+10 (deterministic key `emotional:{date}`), each additional entry that day
+2 (`emotional-entry:{entry_id}`). `local_date` is computed server-side
(clients cannot shift day boundaries — tested with tz-aware input). Midnight
boundaries tested; edit → no re-award; delete → no clawback; pre-existing
day key (simulated race) → only +2; keys persist across restart. Consistency
quest rewards are separate ledger events (`event_type="quest"`), never
confused with entry XP (tested).

## 8. Manual P&L behavior

`user_pnl` is optional, manual-only (create/update/close), accepts
positive/negative/zero/null, is stored verbatim and never computed from
prices/direction (explicit test: entry 100 + exit 110 long → user_pnl stays
null). Never affects XP, levels, quests, achievements or dashboard
progression; the dashboard exposes an informational sum/count echo only.
Closure, edits, deletions award 0 XP.

## 9. Backup & rollback

- Full pre-Phase-2 copy: **`D:\trading strategy\TradeQuest_v1_backup_phase2`**
  (55 files, incl. `data/tradequest.db`, the Excel workbook, all sources).
- `data/tradequest.db` (v1) was never opened for writing by v2 code.
- Rollback: delete `backend/app2`, `backend/tests_v2`, the four root `.bat`
  scripts, `PHASE2_REPORT.md`, and optionally `data/tradequest_v2.db` — or
  restore the whole backup folder over the project.
- Runtime backups: `GET /api/system/backup` (SQLite-consistent copy, last 10).

## 10. Files created / modified / removed

**Created:** `backend/app2/` (16 modules: config, db, models, schemas, main +
services/×6 + routers/×7), `backend/tests_v2/` (9 files, 100 tests),
`start_tradequest_v2.bat`, `start_backend_v2_dev.bat`, `run_tests.bat`,
`setup_tradequest.bat`, `PHASE2_REPORT.md`.
**Modified:** `PHASE1_BLUEPRINT.md` (Appendix P appended; sections A–N
untouched), `README.md` (v2 sections + env table; v1 content intact).
**Removed:** nothing. **Untouched:** entire v1 app (`backend/app`, its
tests), `data/tradequest.db`, frontend, scripts.

## 11–12. Test commands & results (executed)

- `backend\.venv\Scripts\python.exe -m pytest -q` → **179 passed**
  (79 v1 + 100 v2), 0 failures. Baseline before changes: 79 passed.
- `backend\.venv\Scripts\python.exe -m pytest tests_v2 -q` → 100 passed.
- Live smoke via `start_tradequest_v2.bat` (real launch, clean env): server
  bound to `127.0.0.1:8001`, `/api/system/health` ok, fresh empty DB, 23
  quests listed, `data/tradequest_v2.db` created, `tradequest.db` untouched.

## 13. Windows-specific verification

Development, tests and the launch script were all executed on Windows
(PowerShell) in this environment. `setup_tradequest.bat` was **not**
executed (the venv already existed) though it follows the same verified
commands; it is the only script without a live run.

## 14. Known limitations & deferred items

1. **Consistency Quest XP values undecided** (user decision pending).
2. **LQ-02 (Pattern Breaker) deferred** — its Blueprint wording (recurring
   mistake keyword + "worked on it" marking) needs structured mistake tags
   (schema + UI + product decision); deliberately not faked with keyword
   matching. RF-04 and LQ-03 were implemented in the approved correction
   pass (see §16).
3. Quest reward tiers used are 25/50/75/100 — **JM-03 (Log 50) = +75 is
   explicitly approved in the Blueprint quest table** (JM-01..04 =
   +25/+50/+75/+100). Resolved in the correction pass; report updated.
4. Screenshot serving now enforces a resolved-path allow-list
   (`TRADEQUEST2_SCREENSHOT_DIRS`; launch scripts preset
   `%USERPROFILE%\Pictures`). Unconfigured = refused (fail-closed).
   Extension/existence/size checks retained.
5. Single-user, single-process design (by spec); concurrent multi-tab
   writes are safe via SQLite locking + idempotency, but there is no
   multi-user support.
6. Frontend not yet connected to v2 (Phase 3).

## 15. Confirmation

No frontend redesign, no Phase 3 work, and no v1 behavior changes were
made. Phase 3 will begin only after explicit user approval of this report.

## 16. Correction pass (user-approved, post-investigation)

Approved scope executed; all existing rules preserved (XP amounts, claim
workflow, idempotency, transactional ledger, opt-in consistency quests,
historical-label preservation, v1/v2 database separation).

**Implemented:**

1. **JM-03 documentation consistency** — +75 confirmed as Blueprint-approved
   (quest table). Blueprint §XP table annotated; catalog comment corrected;
   regression test `test_jm03_reward_is_exactly_75` added.
2. **RF-04 "Double Take" activated** — Blueprint condition matches exactly
   ("Edit a completed review after ≥7 days"): a review (quick/deep/daily/
   weekly) counts when `updated_at − created_at ≥ 7 days` (boundary
   inclusive), verified purely from persisted rows; editing still awards
   zero XP; completion and one-time claim remain separate. Tests cover
   before/exactly-at/after 7 days, no-XP-on-edit, one-time claim.
3. **LQ-03 "Mentor Voice" activated** — Blueprint wording explicitly
   authorizes the field. Added nullable `weekly_reviews.advice_to_future_me`
   (Text) to the model, `WeeklyReviewIn/Out` schemas (blank → NULL) and the
   evaluator (non-empty advice in ≥4 weekly reviews). Historical rows stay
   NULL and never count; existing v2 databases get the column via an
   idempotent additive `ALTER TABLE` at startup. Tests: valid/missing/
   blank/historical entries, completion, duplicate-claim rejection.
4. **LQ-02 stays deferred** — no keyword matching, no new fields. Required
   for a reliable future implementation: a structured `mistake_tag`
   reference list, an optional `mistake_tags` link on reviews (or a
   mistakes table), a `worked_on` marker on weekly reviews referencing a
   tag, plus UI to select tags — all pending product decisions.
5. **Screenshot allow-list** — new `TRADEQUEST2_SCREENSHOT_DIRS` env var
   (pathsep-separated) + `services/screenshots.py` resolved-path containment
   check (symlinks/junctions/traversal/8.3 resolved by `Path.resolve()`,
   case-insensitive on Windows). Empty config = 422 fail-closed; the launch
   scripts preset `%USERPROFILE%\Pictures`. Extension/existence/25 MB size
   checks and the storage model (text path only) are unchanged. Tests:
   permitted, outside, traversal, junction escape, unconfigured, type,
   missing, oversize, case-insensitivity.
6. **Mutation XP/level feedback** — all create endpoints (trade, quick
   review, deep review, lessons, emotional entry, daily review, weekly
   review) now return `xp_awarded` (the amount the ledger actually inserted
   for that operation, 0 on capped/idempotent cases) and `level_up`
   (`{level, title}` only when that mutation crossed a threshold; else
   `null`). Quest claim responses additionally carry `level_up`. Nothing is
   awarded twice; PATCH responses are unchanged (edits = 0 XP). Additive
   fields — existing clients/tests unaffected. New `tests_v2/test_xp_feedback.py`.

**Test results after the pass:** `pytest -q` → **201 passed** (79 v1 +
122 v2), 0 failures. Live smoke on `127.0.0.1:8001` against the real v2
database: health OK, 23 quests (RF-04/LQ-03 active, LQ-02 deferred, JM-03
= 75), advice column accepted (startup migration applied), `xp_awarded`
returned, `GET /api/system/backup` OK.

**Still requiring user decisions:** Consistency Quest XP values; a
consistency achievements category; Night Shift interpretation (currently
trades, ambiguous vs entries); RF-04's generic tier note (resolved);
default screenshot directory (`Pictures` — changeable via env var).

**Frontend integration notes:** create/claim responses now carry
`xp_awarded`/`level_up`; weekly review payloads accept
`advice_to_future_me`; screenshot serving requires the allow-list env var
(the `.bat` launchers set it — a dev server started manually without it
will refuse screenshots with a clear 422).


