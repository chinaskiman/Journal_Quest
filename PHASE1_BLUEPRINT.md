# Trade Quest — Phase 1 Blueprint

**Product Discovery, Requirements Audit & Technical Architecture**

> Status: Phase 1 complete — planning only. No application code was written and no existing files were modified in this phase. Awaiting approval of the decision list in §N before Phase 2 begins.

Legend: ✅ **Confirmed** (mandated by the brief) · 🔷 **Recommendation** (proposal, safe to adopt) · ⚠️ **Unresolved** (needs your decision)

---

## A. Existing Project Audit

**Archive status:** The originally referenced `Trade_Quest_Final.zip` no longer exists. A `Trade_Quest.rar` (45.8 MB, packed 2026-10-01) exists at `D:\trading strategy\Trade_Quest.rar`. Opened with 7-Zip: 11,466 entries — **a byte-for-byte snapshot of the live project in `D:\trading strategy\Trade_Quest`** (source tree identical, plus `.venv`, `dist`, `data\tradequest.db` included in the archive). The live working copy was audited directly; the archive contains nothing extra. Per the brief: the archive's database and the Excel workbook are **reference only** — the new app starts with a fresh, empty database and imports nothing.

| Aspect | Finding |
|---|---|
| Frontend | React 19 + TypeScript 5.7 + Vite 6; TanStack Query 5, TanStack Virtual 3, Recharts 2, react-router-dom 7 (3 routes); custom CSS, no component library, no icon system (emoji glyphs) |
| Backend | FastAPI + SQLAlchemy 2 + SQLite (WAL); Pydantic v2 validation layer; 4 routers (trades, options, analytics, io); pure calculation engine; Excel importer/exporter (openpyxl); 79 passing pytest tests with temp-DB fixtures |
| Database | 1 SQLite file, 3 tables: `trades` (34-column Excel model: 25 persisted inputs + 9 derived-on-read), `option_values` (5 dropdown lists), `app_state` (kv store) |
| Pages | Journal (virtualized 34-col table, inline edit, drawer, filters, column settings, import/export), Analytics (23 KPIs, charts, 4 group tables), Options (5-list CRUD/reorder) |
| Design assets | Dark "conventional analytics dashboard" theme only — no sci-fi design system, no tokens, no gamification visuals |
| API routes | `/api/trades` CRUD + duplicate + reorder; `/api/options` CRUD; `/api/analytics`; `/api/io/import|export/{journal,analytics,backup}`; `/api/health` |
| Gamification | **None** — no XP, quests, achievements, or progression anywhere |
| Broken/incomplete | Nothing broken. Four features misaligned with the new vision: (1) auto-seeds from the Excel workbook on first boot; (2) computes Net PnL from prices — new spec forbids inferring results; (3) finance-centric analytics dashboard; (4) Excel-specific importer/exporter |

**Reuse plan**

| Keep & adapt | Redesign / replace |
|---|---|
| FastAPI + SQLAlchemy + SQLite skeleton (`db.py`, `config.py` env-var pattern, router/schemas/validation layering) | `models.py` → new normalized schema (§H) |
| Pytest fixture infrastructure (temp DB via env var) | `calculations.py` engine → **retired**; manual results only |
| TanStack Query client pattern + SPA-served-by-FastAPI single-port launch | `AnalyticsPage` → replaced by Quest Hub / progression UI |
| Options CRUD UI logic → becomes Symbols/Setups/Emotions managers | Excel `importer.py` → retired (kept in repo as reference, out of the new app path) |
| Table virtualization technique (if the trade list needs it) | `exporter.py` → replaced by generic SQLite/JSON backup service |
| Vite proxy + build pipeline, `.bat`-friendly layout | `styles.css` → entirely new design system (§E) |

## B. Product Requirements Matrix

| # | Section | Purpose | Core actions | Required fields | Saves | Gamification link | Depends on |
|---|---|---|---|---|---|---|---|
| 1 | Dashboard / Quest Hub | Mission-control home; "what should I do now & where am I?" | View level/XP, active quests, one-click capture, activity feed | — | nothing (nav only) | Displays all progression | All sections |
| 2 | Trade Journal | Full record of executed trades | Create/edit/delete, filter, close trade with manual result, open reviews | symbol†, opened_at, direction†, setup†, notes, screenshot path, result (manual: Win/Loss/BE)† | trades | Prerequisite for review quests; milestones count *records*, never P&L | Settings |
| 3 | Quick Capture | Fast entry of an already-executed trade (<30s) | Minimal form → creates open trade record | symbol, direction, opened_at, setup (opt), one-line thesis | trades (status=open) | **+20 XP** once per trade | Settings |
| 4 | Quick Review | 60-second post-trade reflection | Rate execution, note what went well/wrong/improve | execution rating 1–5, 3 short texts | quick_reviews (1 per trade) | **+15 XP** once per trade | Trade Journal |
| 5 | Deep Review | Structured forensic review | Fill 5 sections, grade, extract lessons | 5 text sections, grade, lessons[] | deep_reviews, lessons | **+30 XP**; **+10 XP per lesson** (cap §D) | Trade Journal |
| 6 | Emotional Journal | Standalone emotional reflection, linked or unlinked | Create entry, tag emotion + intensity, optional trade link | emotion label†, intensity 1–5, body text, trade link (opt) | emotional_entries | **+10 XP** ⚠️ (first/day — decision 1) | Settings |
| 7 | Daily Review | End-of-day reflection | Mood/energy/focus, reflection, lesson of the day | review_date (unique), ratings, text | daily_reviews | **+15 XP** once per calendar day | — |
| 8 | Weekly Review | Weekly retrospective | Highlights/challenges/patterns/next-week plan | ISO year+week (unique), 4 text fields | weekly_reviews | **+30 XP** once per ISO week | — |
| 9 | Quest Center | Browse/track all quests | View available/active/completed, progress bars | — | quest_progress (auto) | Quest completion grants bonus XP (§D) | Gamification engine |
| 10 | Achievements | Trophy hall | Browse categories, states, unlock history | — | achievement_unlocks | Pure display of unlock history | Gamification engine |
| 11 | Settings | Manage lists + preferences | CRUD symbols/setups/emotions, toggle UI prefs, backup/restore | list names† | symbols, setups, emotions, ui_preferences | Feeds all dropdowns; snapshot rules protect history (§H) | — |

† = validated against settings lists at creation time.

## C. Final Navigation Structure

🔷 **Recommended structure** (all 11 sections remain reachable; two are elevated to global actions to reduce sidebar noise):

```
┌─ Sidebar ───────────────────────┐
│  ◈ TradeQuest          [L7 • XP bar]   ← persistent mini HUD
│                                 │
│  HUB                             │
│   ▸ Quest Hub (Dashboard)        │
│                                 │
│  JOURNAL                         │
│   ▸ Trade Journal                │
│                                 │
│  REFLECTION                      │
│   ▸ Reviews  (tabs: Quick | Deep | Emotional | Daily | Weekly) │
│                                 │
│  PROGRESSION                     │
│   ▸ Quest Center                 │
│   ▸ Achievements                 │
│                                 │
│  SYSTEM                          │
│   ▸ Settings                     │
└─────────────────────────────────┘
[＋ Quick Capture]  ← global button in top bar, always available (hotkey Ctrl+K / "N")
```

- **Quick Capture** is a global modal (from any page) *and* a primary CTA on the dashboard — a dedicated nav page would waste a slot for a 4-field form.
- **Quick Review / Deep Review** are primarily opened *per trade* (from journal rows and the trade drawer) — their tab in "Reviews" lists review activity across all trades so the functionality stays independently discoverable.
- Emotional Journal, Daily and Weekly Reviews get dedicated tabs with prominent "due today / due this week" hints on the dashboard (gentle, never punishing).
- Nav badge dots: unseen achievement unlocks, unreviewed trades count.

## D. Gamification Design

### XP event model

A single append-only **ledger** (`xp_events`) is the only source of truth for XP. Every award carries a unique **idempotency key**; the DB `UNIQUE` constraint is the duplicate firewall.

```
xp_events: id | amount | reason_code | idempotency_key (UNIQUE) | source_type | source_id | awarded_at
```

| XP reason | Amount | Idempotency key | Awarded when |
|---|---|---|---|
| Quick Capture | **+20** ✅ | `capture:{trade_id}` | trade created via Quick Capture or Journal form |
| Quick Review | **+15** ✅ | `qreview:{review_id}` | first save of a trade's quick review |
| Deep Review | **+30** ✅ | `dreview:{review_id}` | first save of a trade's deep review |
| Meaningful lesson | **+10** ✅ | `lesson:{lesson_id}` | lesson row created (from any review type) |
| Daily Review | **+15** ✅ | `daily:{yyyy-mm-dd}` | first save of that date's review |
| Weekly Review | **+30** ✅ | `weekly:{iso_year}-W{ww}` | first save of that week's review |
| Emotional entry | 🔷 **+10**, first entry per calendar day only (0 afterwards) | `emotional:{date}` | prevents spam-farming while valuing reflection — ⚠️ decision 1 (brief omitted it) |
| Quest completion | 🔷 +25 (tier 1) / +50 (tier 2) / +100 (tier 3); JM-03 "Log 50" = **+75** per the quest table below (approved) | `quest:{code}` | quest auto-completes |
| Editing any record | **+0** always ✅ | — | PATCH never awards |
| Closing a trade | 🔷 +0 (alternative +5) | — | decision 2 — recommendation: 0, to avoid pressuring trade completion |

**Duplicate-prevention rules (✅):**

1. XP is awarded **once, server-side, at first creation/save** of the linked record — the idempotency key makes a second award impossible even under double-submit or retry.
2. Edits/PATCH never award and never remove.
3. Deletes never claw back (ledger is immutable history) — no negative feedback loops; quest *counters* may drop if records are deleted, but a **completed quest/achievement stays completed forever**.
4. The API response of a creating call includes `xp_awarded` (0 on re-save) so the UI shows accurate feedback without re-querying.
5. Lesson XP is capped at **3 lessons per parent review** (further lessons save fine, no XP) 🔷.

### Levels

🔷 Transparent formula (shown in UI tooltip): **XP to advance from level n → n+1 = 100 + 50·(n−1)** → cumulative thresholds: L2=100, L3=250, L4=450, L5=700, L6=1000, L7=1350, L8=1750, L9=2200, L10=2700… (~40–60 typical activities to reach the common upper range). Levels reflect *journaling progression only* — never trading skill or money (✅).

| Lvl | Title | | Lvl | Title |
|---|---|---|---|---|
| 1 | Drifter | | 9 | Pattern Seeker |
| 2 | Signal Listener | | 10 | Cartographer of Habits |
| 3 | Log Keeper | | 11 | Archivist of Self |
| 4 | Deck Observer | | 12 | Mission Specialist |
| 5 | Flight Cadet | | 13 | Sector Commander |
| 6 | Junior Analyst | | 14 | Quest Master |
| 7 | Chronologist | | 15+ | Legend of the Quest (mastery tier) |
| 8 | Mirror Navigator | | | |

### Quest catalog

Definitions live in a versioned **code catalog** 🔷 (no seed tables to drift); progress is auto-tracked from real saved data.

| Code | Name | Category | Trigger condition | Reward |
|---|---|---|---|---|
| FT-01 | First Contact | First-time | Create first trade | +25 |
| FT-02 | First Reflection | First-time | Complete first Quick Review | +25 |
| FT-03 | Deep Diver | First-time | Complete first Deep Review | +25 |
| FT-04 | Heart on Sleeve | First-time | First Emotional Journal entry | +25 |
| FT-05 | Day One | First-time | First Daily Review | +25 |
| FT-06 | Week One | First-time | First Weekly Review | +25 |
| FT-07 | Chart Your World | First-time | Create first symbol & first setup in Settings | +25 |
| RF-01 | Reflect ×5 | Reflection | Quick Review 5 trades | +50 |
| RF-02 | Know Thyself | Reflection | 3 emotional entries linked to trades | +50 |
| RF-03 | The Autopsy | Reflection | 5 Deep Reviews completed | +50 |
| RF-04 | Double Take | Reflection | Edit a completed review after ≥7 days | +25 |
| JM-01..04 | Log milestones | Milestones | Log 10 / 25 / 50 / 100 trades | +25/+50/+75/+100 |
| JM-05 | Stargazer | Milestones | 100 total XP earned | +25 |
| JM-06 | Chronicler | Milestones | 30 lessons documented | +50 |
| CN-01..03 | Consistency | Consistency (⚠️ **opt-in toggle**, off by default) | Daily Reviews on 3 / 7 / 21 distinct days — *counted, never streak-reset; missed days are simply not counted, nothing is lost* | +25/+50/+100 |
| LQ-01 | Curious Mind | Learning | 5 lessons from Deep Reviews | +50 |
| LQ-02 | Pattern Breaker | Learning | Same mistake keyword documented 3×, then marked "worked on it" in a Weekly Review | +50 |
| LQ-03 | Mentor Voice | Learning | "Advice to future me" written in 4 Weekly Reviews | +50 |

✅ No quest pressures trading more; no penalties; consistency quests are opt-in and non-punishing.

### Achievements

- **Categories:** Initiation (firsts) · Reflection (review depth) · Consistency (opt-in only) · Knowledge (lessons) · Curation (settings/lists) · Secrets (hidden until unlocked, e.g. *Night Shift* — first entry logged 00:00–05:00; *The Phoenix* — first "Loss" trade given a full Deep Review).
- **Visual states:** Locked (dim tile, condition text visible) · Unlocked (gold ring + cyan glow + unlock date) · Hidden/secret (silhouette "???" tile). Tiers rendered as bronze/silver/gold frame colors.
- **Persistence:** `achievement_unlocks` (code PK, unlocked_at, seen_at for the notification dot) — immutable once written.

### Progression map 🔷

A **vertical "sector track"** in the Quest Center: one sector per level band; nodes = quests/milestones. States: completed (lit cyan node, gold ring), current (pulsing halo), locked (dim). Pure CSS/SVG — no heavy dependency. The optional animated car/road is **deferred** (⚠️ decision 6) — the sector track delivers the game-feel with far less motion risk.

### Reward feedback (non-disruptive)

- XP gain → compact toast top-right "+20 XP — Quick Capture" (2.5 s) + header XP bar animates.
- Level-up → brief centered overlay ("LEVEL 7 — CHRONOLOGIST") with dismiss; reduced-motion variant = static fade.
- Achievement → toast with badge icon + "View" deep-link; nav dot until visited.
- Sounds: **off by default**, toggle in Settings.
- All feedback respects `prefers-reduced-motion` + user toggle.

## E. Visual Design System

**Palette (design tokens):**

| Token | Value | Use |
|---|---|---|
| `bg-void` | `#070B14` | app background (deep navy / near-black) |
| `bg-panel` / `bg-elevated` | `#0D1420` / `#131C2C` | cards / panels |
| `border-subtle` | `#1E2A3F` | panel borders |
| `gold` / `brass` | `#D4AF6A` / `#A98B5F` | XP, level ring, achievement frames |
| `cyan` / `electric` | `#38E1F0` / `#4D9FFF` | interactive highlights, active quest glow |
| `text-1 / 2 / 3` | `#E8EDF5` / `#93A1B8` / `#5C6B84` | text hierarchy |
| `success / warn / danger` | `#3DDC97` / `#FFC757` / `#FF6B7A` | semantic states |

- **Typography:** body = system stack (Segoe UI Variable → Inter fallback); display/headings = self-hosted sci-fi font (Orbitron or Rajdhani, woff2 bundled locally — no CDN) 🔷; numbers = `font-variant-numeric: tabular-nums` + Cascadia Code/Consolas.
- **Surfaces:** 12px radius, 1px subtle border, faint inner gradient; sci-fi corner notches via CSS clip-path on hero panels; **glow reserved for interactive/active states only** (restraint).
- **Motion:** 150–250 ms ease-out; XP-bar fill, node pulse, toast slide; `prefers-reduced-motion` + user toggle kill all movement (opacity fades only).
- **Navigation:** 240px left sidebar, collapsible to 64px icon rail; lucide-react as the sole new frontend dependency for icons 🔷 (tree-shaken; alternative: hand-rolled SVGs).
- **Forms/tables:** dark inputs with cyan focus ring; sticky-header tables, subtle zebra, hover lift.
- **Empty states:** every page ships a themed empty state ("Space awaits — log your first trade") with a direct CTA.
- **Narrow windows:** ≤1024px sidebar auto-collapses; ≤720px drawers become bottom sheets; dashboard grid reflows to 1 column (desktop app — mobile is best-effort only).

## F. Dashboard Textual Wireframe

```
┌────────────────────────────────────────────────────────────────────────┐
│ ◈ TRADEQUEST          [＋ Quick Capture]            🔔0  ⚙ Settings      │
├────────────────────────────────────────────────────────────────────────┤
│ ╔═ PILOT STATUS ═════════════════════════════════════════════════════╗ │
│ ║  ( L7 )   CHRONOLOGIST                          LEVEL 8 IN 150 XP   ║ │
│ ║  level ring                               ████████████░░░░  +150 XP   ║ │
│ ║  ── 1,840 XP total ── 12 quests ── 9 achievements ──────────────    ║ │
│ ╚════════════════════════════════════════════════════════════════════╝ │
│ ╔═ ACTIVE QUESTS ══════════════╗ ╔═ TODAY ═══════════════════════════╗ │
│ ║ ◈ Reflect ×5        3/5 ██░ ║ ║ Daily Review    [due • +15XP] →     ║ │
│ ║ ◈ Log 10 trades     7/10 █░ ║ ║ Quick Capture   [log a trade]  →   ║ │
│ ║ ◈ Deep Diver       1/5  ░  ║ ║ Weekly Review   [opens Sat]        ║ │
│ ╚═════════════════════════════╝ ╚════════════════════════════════════╝ │
│ ╔═ UNREVIEWED TRADES ══════════╗ ╔═ RECENT ACTIVITY ══════════════════╗│
│ ║ XAUUSD Long  Sep 30  [QR][DR]║ ║ +30 XP  Deep Review · EURUSD  2h   ║│
│ ║ EURUSD Short Sep 29  [QR][DR]║ ║ ★ Achievement · Heart on Sleeve   ║│
│ ╚══════════════════════════════╝ ╚════════════════════════════════════╝│
└────────────────────────────────────────────────────────────────────────┘
```

## G. Quest Center Textual Wireframe

```
┌────────────────────────────────────────────────────────────────────────┐
│ QUEST CENTER                        filter: [All|Active|Done|Secrets]   │
│ ╔═ PROGRESSION MAP ─═════════════════════════════════════════════════╗ │
│ ║  SECTOR 6 ─ ●──●──●──◍──○──○     ● done  ◍ current  ○ locked       ║ │
│ ║  SECTOR 7 ─ ○──○──○──○──○──○                                       ║ │
│ ╚══════════════════════════════════════════════════════════════════════╝ │
│ ┌─ ACTIVE ────────────────┐ ┌─ AVAILABLE ──────────┐ ┌─ COMPLETED ────┐ │
│ │ ◈ Reflect ×5      3/5  │ │ ◈ Week One      new! │ │ ✓ First Contact │ │
│ │   bar ██░░░  +50XP     │ │   first weekly review│ │  Sep 12 · +25   │ │
│ │   [View trades→]       │ │   [Start →]  +25XP   │ │ ✓ Day One       │ │
│ └────────────────────────┘ └──────────────────────┘ └─────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

## H. Database Schema Proposal

Fresh SQLite file (`data/tradequest.db`), normalized, ~14 tables. **All labels that appear in historical records are stored as text snapshots** (denormalized by design) so renames/archives never rewrite history ✅.

**Lookup lists** (identical shape): `symbols`, `setups`, `emotions` — `id PK · name TEXT UQ · sort_order INT · is_active BOOL (default 1) · created_at · updated_at`. Index on `(is_active, sort_order)`.
**Rules ✅:** *rename* → future picks only, old snapshots untouched; *disable* → hidden from pickers, history intact; *delete* → **soft by default** (`is_active=0`); hard delete permitted only when unreferenced (API checks references, else 409).

**trades** — `id PK · status CHECK(open|closed) default open · symbol_label TEXT · setup_label TEXT NULL · direction CHECK(long|short) NULL · opened_at DATETIME · closed_at DATETIME NULL · result CHECK(win|loss|breakeven) NULL ← **manual only, never derived** ✅ · result_note TEXT NULL · screenshot_path TEXT NULL ← **raw user path only, bytes never stored** ✅ · thesis TEXT · notes TEXT · user_pnl REAL NULL (⚠️ decision 3) · created_at · updated_at · deleted_at NULL (soft delete 🔷)`. Indexes: `(status)`, `(opened_at)`, `(symbol_label)`.

**quick_reviews** — `id PK · trade_id FK→trades UNIQUE · followed_plan CHECK(yes|partly|no) NULL · execution_rating INT 1–5 · went_well TEXT · went_wrong TEXT · improve TEXT · created_at · updated_at`.

**deep_reviews** — `id PK · trade_id FK→trades UNIQUE · plan_review · execution_review · risk_review · emotions_review · mistakes · grade CHECK(A|B|C|D|F) NULL · key_takeaway · created_at · updated_at`.

**lessons** — `id PK · source_type CHECK(quick|deep|daily|weekly|emotional) · source_id INT NULL · trade_id FK NULL · text NOT NULL · created_at`. Index `(source_type, source_id)`.

**emotional_entries** — `id PK · trade_id FK NULL (unlinked = standalone ✅) · occurred_at DATETIME · emotion_label TEXT NOT NULL (snapshot) · intensity INT 1–5 · trigger TEXT · body TEXT · created_at · updated_at`. Indexes: `(occurred_at)`, `(trade_id)`.

**daily_reviews** — `id PK · review_date DATE UNIQUE · energy INT 1–5 NULL · focus INT 1–5 NULL · mood INT 1–5 NULL · reflection TEXT · created_at · updated_at`.

**weekly_reviews** — `id PK · iso_year INT · iso_week INT · UNIQUE(iso_year, iso_week) · highlights · challenges · patterns · plan_next_week · created_at · updated_at`.

**xp_events** — `id PK · amount INT · reason_code TEXT · idempotency_key TEXT UNIQUE · source_type TEXT NULL · source_id INT NULL · awarded_at`. Index `(awarded_at)`. Append-only, never updated/deleted ✅.

**quest_progress** — `id PK · quest_code TEXT UNIQUE · progress_current INT · completed_at NULL`. Quest/achievement *definitions* live in a versioned code catalog 🔷 (no seed tables to drift).

**achievement_unlocks** — `code TEXT PK · unlocked_at · seen_at NULL`.

**ui_preferences** — `key TEXT PK · value TEXT (JSON)`.

**app_meta** — `schema_version · installed_at · last_backup_at` (kv).

**Deletion & historical-preservation rules:** reviews cascade only on hard trade delete (soft delete is the default, so this is rare); xp_events survive any deletion (no clawback); daily/weekly uniqueness prevents duplicates; all FK-bearing historic labels are snapshots → **history is immutable to settings changes** ✅.

## I. API Endpoint Proposal (all under `/api`, FastAPI routers)

| Method · Path | Purpose | Payload → Response | Validation & errors |
|---|---|---|---|
| `GET /trades` | List/filter/paginate | `?status&symbol&result&q&sort&page` → page | 422 bad params |
| `POST /trades` | Create (Quick Capture & full form) | trade body → trade + `xp_awarded` | symbol†/setup† must be active list item → 422; label snapshot stored |
| `GET/PATCH/DELETE /trades/{id}` | Read / edit / soft-delete | PATCH body → trade (no XP) | 404; result field ignored on open trades |
| `POST /trades/{id}/close` | **Manual closure** ✅ | `{result: win\|loss\|breakeven, result_note?, closed_at}` → trade | 404; 409 already closed; 422 missing result — **server never computes result** |
| `GET/POST /trades/{id}/quick-review` · `PATCH /quick-reviews/{id}` | Quick Review CRUD | review body → review + `xp_awarded` | 409 if exists (one per trade); PATCH no XP |
| `GET/POST /trades/{id}/deep-review` · `PATCH /deep-reviews/{id}` | Deep Review CRUD | body + `lessons[]` → review + `xp_awarded` | 409; lesson XP cap 3 |
| `GET /lessons` | Lesson library | `?source_type&q` → list | — |
| `GET/POST /emotional-entries` · `GET/PATCH/DELETE /emotional-entries/{id}` | Emotional journal CRUD | entry body (trade_id optional) → entry + `xp_awarded` | emotion† from list; 404 on bad trade link |
| `GET /daily-reviews` · `GET/POST /daily-reviews/{date}` · `PATCH` | Daily review | date-keyed body → review | 409 duplicate date; ISO date format |
| `GET /weekly-reviews` · `GET/POST /weekly-reviews/{year}/{week}` · `PATCH` | Weekly review | week-keyed body → review | 409 duplicate week |
| `GET/POST /settings/{symbols\|setups\|emotions}` · `PATCH/DELETE /settings/{list}/{id}` | List CRUD | name, sort, is_active | 409 delete-if-referenced; rename allowed freely |
| `GET/PATCH /preferences` | UI prefs kv | `{key:value}` | — |
| `GET /dashboard` | One-shot hub payload | → pilot status, active quests, today, unreviewed, feed | — |
| `GET /xp` | Summary + history | `?page` → `{total, level, next_threshold, events[]}` | — |
| `GET /quests` | Catalog + live progress | → grouped quest cards | — |
| `GET /achievements` | Catalog + unlock states | → tiles with states | — |
| `POST /achievements/{code}/seen` | Clear nav dot | → ok | 404 unknown code |
| `GET /system/backup` | Download timestamped SQLite copy 🔷 | → file | — |
| `POST /system/restore` | Restore from backup file | upload → report | 409 unless confirm flag |
| `GET /assets/screenshot` | **Stream** image from user-supplied path at render time (bytes never stored ✅) | `?path=` → image | 404 missing; 415 non-image ext; strict path validation |
| `GET /health` | Startup smoke | → ok | — |

† = validated against settings lists. Gamification is **not** a separate API surface — XP/quest/achievement evaluation happens transactionally inside the write endpoints (same DB transaction as the record insert), guaranteeing consistency.

## J. Frontend & Backend Architecture

**Stack ✅:** React + TypeScript + Vite (existing project) · FastAPI + SQLite · Pytest + Vitest/RTL 🔷 (new dev-only deps).

```
Trade_Quest/
├─ start.bat / dev.bat / test.bat          ← Windows launch scripts ✅
├─ backend/app/
│   ├─ main.py  config.py (env overrides, bind 127.0.0.1 ✅)  db.py
│   ├─ models.py  schemas.py  validation.py
│   ├─ gamification/  xp_ledger.py  levels.py  quests.py  achievements.py  catalog.py
│   ├─ routers/  trades.py  reviews.py  emotional.py  checkins.py  settings.py
│   │            gamification.py  dashboard.py  system.py
│   └─ backup.py
├─ backend/tests/           (pytest, temp DB via TRADEQUEST_DB env ✅)
└─ frontend/src/
    ├─ pages/  QuestHubPage  JournalPage  ReviewsPage(+tabs)  QuestCenterPage
    │          AchievementsPage  SettingsPage
    ├─ components/  Panel  StatChip  QuestCard  BadgeTile  XPBar  LevelRing
    │               Toast  Modal  Drawer  EmptyState  Field  …
    ├─ gamification/  useLevel  useXpToast  rewardBus
    ├─ api/  client.ts (typed, TanStack Query)
    ├─ design/  tokens.css (palette/typography/motion)
    └─ App.tsx (router + sidebar + global Quick Capture + toast host)
```

- **Communication:** REST + JSON over `http://127.0.0.1:8000`; TanStack Query for all server state; Vite proxy in dev; FastAPI serves built SPA single-port in production (proven pattern from existing project).
- **Startup:** `start.bat` → activates venv, starts uvicorn on **127.0.0.1:8000**, opens default browser; `dev.bat` → uvicorn --reload + `npm run dev` + open :5173. Fresh DB auto-created on first run, **no seeding** ✅.
- **Error handling:** typed error envelope (`{detail, code}`) → toast mapping; React ErrorBoundary per page; backend transactional writes (record + XP in one commit).
- **Backups:** manual download endpoint + auto copy on each launch (keep last 10) 🔷 + restore flow.
- **Security/privacy:** loopback-only binding, no accounts, no cloud, no telemetry; CORS locked to localhost origins; screenshot endpoint validates extension/existence (local single-user threat model); WAL journaling for durability.

## K. User Workflows

**1. New user opening the empty application** — Fresh DB auto-created on first launch (no seeding, no old data) → Dashboard shows the **"Pilot Initiation"** empty state: level ring "L1 · Drifter · 0 XP", zero-quest placeholders, and a 3-step starter card (*define a symbol → log a trade → write your first review*) → first-time quests FT-01…FT-07 appear in Quest Center as the onboarding ladder → each completion lights a node and grants its bonus.

**2. Recording an already-executed trade** — Top-bar **[＋ Quick Capture]** (or dashboard CTA) → modal: symbol (from list, with inline "add new symbol" chip), direction, opened_at (defaults to now), optional setup, one-line thesis, optional screenshot path, optional emotion tags → `POST /trades` → **+20 XP** (`capture:{id}`) → toast + XP bar animation; trade appears in Journal as `open`.

**3. Editing a trade** — Journal row → drawer → edit fields → `PATCH` → **no XP, no new events**. If the symbol was renamed in Settings since creation, the trade still displays its original snapshot label; changing the symbol re-snapshots to the newly picked label.

**4. Closing a trade with a manually selected result** — Drawer → **Close Trade** → user explicitly selects **Win / Loss / Breakeven** (+ optional note, closed_at) → `POST /trades/{id}/close` → status `closed`. **The server never computes or infers the result from any price/direction field** ✅. UI gently suggests (never forces) a Quick Review for the freshly closed trade.

**5. Completing Quick Review** — From the trade row/drawer or Reviews tab → followed-plan choice, execution rating 1–5, what went well / wrong / improve → **+15 XP once** (`qreview:{id}`); later edits via PATCH award nothing.

**6. Completing Deep Review** — Drawer → Deep Review → five structured sections (plan, execution, risk, emotions, mistakes) + self-grade + lessons list. Each lesson row is saved to the lessons table → **+10 XP each** (capped at 3 per review) plus **+30 XP** for the review itself. RF-03/LQ-01 counters advance.

**7. Creating an independent Emotional Journal entry** — Reflection → Emotional tab → New Entry: emotion (from list), intensity 1–5, trigger, reflection text, occurred_at, **no trade link** → **+10 XP** (first entry per calendar day) → appears in the emotional timeline.

**8. Linking an emotional entry to a trade** — Either pick the trade during creation, or open an existing entry → "Link to trade" → `PATCH` with `trade_id`. Linking/unlinking **never awards XP** (it's an edit). The trade drawer shows linked emotional entries.

**9. Completing Daily Review** — Dashboard "due today" card or Reflection → Daily tab → energy/focus/mood sliders + free reflection → **+15 XP once per calendar date** (`daily:{date}`). Reopening the same date loads the saved review for editing (no re-award); a different date starts a new review.

**10. Completing Weekly Review** — Reflection → Weekly tab (current ISO week pre-selected, past weeks viewable) → highlights / challenges / patterns / plan for next week → **+30 XP once per ISO week** (`weekly:{year}-W{week}`).

**11. Unlocking a quest** — Fully automatic: every write endpoint runs the gamification evaluator **inside the same DB transaction** as the record insert. When a catalog condition's threshold is crossed, `quest_progress.completed_at` is set, bonus XP is appended (`quest:{code}`), toast fires, Dashboard/Quest Center data refreshes. No manual claim step 🔷.

**12. Unlocking an achievement** — Same transactional evaluation → `achievement_unlocks` row written (immutable) → toast with badge + "View" deep link → nav dot until `POST /achievements/{code}/seen`. Hidden/secret achievements flip from "???" to their true art on unlock.

**13. Leveling up** — If an XP insert crosses the next threshold, the mutation response carries `level_up: {level, title}` → centered overlay ("LEVEL 7 — CHRONOLOGIST"), XP bar refills toward the next threshold, next sector band becomes visible on the map. Reduced-motion users get a static fade variant.

**14. Editing a previously completed record without duplicate XP** — Any PATCH → the gamification service is **not invoked for updates**; the `idempotency_key UNIQUE` constraint is the hard guarantee. Creation responses include `xp_awarded` (0 for edits), and each reviewed record displays a "Reviewed · +15 XP · Sep 30" badge so users never expect double rewards.

### Edge cases & special flows

| # | Case | Handling |
|---|---|---|
| E1 | Attempting a second Quick Review for the same trade | API 409 + UI redirects to edit mode of the existing review; no XP |
| E2 | Renaming/archiving/deleting a symbol in Settings | Historical trades keep snapshot labels; disabled symbols leave pickers only; hard delete → 409 while referenced |
| E3 | Screenshot path invalid or file moved | Trade record never breaks — thumbnail shows "image unavailable" placeholder; re-link via edit |
| E4 | Deleting a trade that has reviews / emotional links | Soft delete by default (drawer "Delete" = soft, restores possible 🔷); hard delete cascades reviews, XP ledger untouched |
| E5 | Clock/timezone quirks at midnight | All uniqueness keys derive from **local date** (daily) and **ISO year-week** (weekly); SQLite stores ISO-8601 local time |
| E6 | Offline / server not running | Frontend fetch interceptor → persistent "Connection lost — retrying" banner; optimistic updates disabled for writes |
| E7 | Long text volumes (multi-page weekly reflections) | TEXT columns unbounded; frontend uses auto-growing textareas; list queries exclude bodies by default |
| E8 | Installing/running on a second machine | Copy project + `data/tradequest.db` (or restore from a backup file) — single-file SQLite portability ✅ |
| E9 | Backdated Quick Capture (trade opened days ago) | Allowed; opened_at is user-editable; XP keyed to creation, not entry date |
| E10 | Backdated Daily/Weekly Reviews | Allowed to fill missed dates/weeks — each distinct date/week still earns its once-off XP (CN quests count distinct days, no streak reset) |
| E11 | User tries to close an already-closed trade | 409; UI shows result-change flow (edit result + note, no XP) |
| E12 | Empty settings lists on first run | Journal/emotional forms show "add your first symbol/emotion" inline create chips |

## L. Test Strategy

**Backend (pytest, existing temp-DB fixture pattern):**

- **XP idempotency:** identical POST twice (double-submit simulation) → 1 ledger row, 1× XP; PATCH → no rows; DELETE trade → ledger intact.
- **Ledger arithmetic:** create 3 review types + lessons → exact `xp_events` rows; total = sum; lesson cap at 3 enforced.
- **Level thresholds:** parameterized tests for boundaries (100, 250, 450…) and just-below/just-above values; titles map correctly.
- **Quest engine:** FT/RF/JM progression; completion writes bonus XP + sets `completed_at` exactly once; counters never decrease completed quests; CN quests respect opt-in toggle.
- **Achievements:** unlock once, immutable; `seen_at` flow; hidden achievements only reveal after unlock.
- **Manual results rule:** close endpoint requires explicit `win|loss|breakeven`; no endpoint computes result ✅.
- **Snapshot immutability:** rename symbol → old trade label unchanged; disable → hidden from pickers, history intact; delete-referenced → 409.
- **API contract:** each endpoint's 200/404/409/422 matrix; pagination; date/week uniqueness.

**Frontend (Vitest + React Testing Library 🔷):** XP toast on awarded response; level-up overlay on `level_up` payload; XP bar math (current/next thresholds); quest card progress %; empty states render CTAs; reduced-motion class disables animations; forms validate symbol-from-list + inline-create chip.

**End-to-end smoke 🔷:** script drives: create settings items → quick capture → close trade → quick review → deep review + lessons → daily + weekly review → verify pilot status, one active quest advanced, XP ledger totals — asserting the full loop with a real server.

## M. Development Roadmap

| Phase | Deliverables | Estimate 🔷 |
|---|---|---|
| 2 · Backend foundation | New schema (create_all, fresh DB), gamification core (ledger, levels, quest catalog, transactional award service), trades CRUD + manual close, settings lists + snapshot rules, dashboard endpoint, core pytest suites | ~2 sessions |
| 3 · UI foundation | Design tokens + base components (Panel/Toast/Modal/Drawer/XPBar), new shell (sidebar + global Quick Capture), Journal page, Settings pages, API client rewrite | ~2 sessions |
| 4 · Reviews module | Quick/Deep/Emotional/Daily/Weekly review UIs + endpoints, lessons, trade drawer with all review entry points | ~1.5 sessions |
| 5 · Gamification UI | Quest Center + progression map, Achievements hall, dashboard wiring, toasts/level-up overlay, nav badges, sound toggle | ~1.5 sessions |
| 6 · Polish & hardening | Backup/restore flow, E2E smoke, reduced-motion + empty states, performance pass, README/scripts update, final regression | ~1 session |

Each phase ends with a runnable, tested increment (start.bat boots the app, pytest green, no regressions).

## N. Risks & Unresolved Questions

**Risks / opportunities:** (1) *Scope discipline* — gamification grows feature-by-feature; the code catalog + ledger design keeps additions cheap. (2) *Data migration anxiety* — fresh DB means zero migration risk, but the user must accept a blank slate (mitigated by backup/restore tooling). (3) *Motivation backfire* — counters must never imply trading skill; all copy reviewed to reward journaling only. (4) *Motion sensitivity* — reduced-motion is a first-class path, not an afterthought. (5) *Icon/asset sprawl* — one icon library (lucide-react 🔷), one display font, self-hosted. (6) *Dev-env drift* — port 8000 conflicts already bitten once on this machine (stale uvicorn processes); scripts will bind 127.0.0.1 explicitly and check/clear the port before launch.

### Decisions awaiting your approval

| # | Item | Recommendation |
|---|---|---|
| 1 | Emotional-entry XP rule (brief omitted it) | +10 XP for the **first entry per calendar day** (0 after) — prevents spam-farming while still valuing reflection |
| 2 | XP for closing a trade | **+0** (alternative: +5). Recommend 0 so trade lifecycle never competes with reflection |
| 3 | Optional `user_pnl` field (user-typed P&L, manual, off by default) | Include in schema as nullable column + Settings toggle to show the field; UI *never* computes or sums it |
| 4 | Lesson XP cap | **3 lessons per review** earn XP (extra lessons save fine, no XP) |
| 5 | Quest claim flow | **Fully automatic** completion + XP on threshold cross; no claim button |
| 6 | Progression map style | **Sector-track map** (CSS/SVG, low risk); animated car/road deferred to a later phase if wanted |
| 7 | New dependencies | `lucide-react` (icons) + **Orbitron** (self-hosted woff2) + Vitest/RTL (dev-only). All tree-shaken, no CDN at runtime |
| 8 | Consistency quests (CN-01..03) | **Opt-in toggle, off by default**; count distinct days, never streak-reset |
| 9 | v2 build location | Build **in-place** in `D:\trading strategy\Trade_Quest` (git branch or rely on `.rar` archive as the v1 snapshot) |
| 10 | This blueprint document | Save as `PHASE1_BLUEPRINT.md` in the repo — ✅ done, this file |

**Next step:** approve or adjust the items above, and Phase 2 (Backend foundation) begins immediately: new normalized schema, gamification core (XP ledger, levels, quest catalog, transactional award service), trades CRUD + manual close endpoint, settings lists with snapshot rules, dashboard endpoint, and core pytest suites.

---
*End of Phase 1 blueprint. Sections A–N complete. No application code was changed or created during Phase 1; this document is the sole Phase 1 artifact.*

---

# APPENDIX P — Phase 2 As-Built (Backend Foundation & Progression Systems)

*Status: IMPLEMENTED and tested (see PHASE2_REPORT.md). This appendix records
the final approved Phase 2 decisions and any deviations from the Phase 1
design above. It is the authoritative backend reference.*

## P.1 Architecture (as built)

- New self-contained backend package **`backend/app2/`** — a deliberate
  deviation from "replace `backend/app` in place", chosen to guarantee:
  zero risk to the legacy database, an intact v1 app + its 79 tests as a
  working rollback, and no frontend breakage during the backend phase.
  Phase 3 will promote `app2` to the primary app alongside the frontend
  redesign.
- Fresh SQLite database **`data/tradequest_v2.db`** (env override
  `TRADEQUEST2_DB`). The legacy `data/tradequest.db` is never read, written,
  or migrated. No Excel auto-seeding exists in `app2` (the v1 importer is not
  imported); no demo trades, no fake XP, no automatic P&L.
- Layering: `models.py` (SQLAlchemy 2) → `schemas.py` (Pydantic v2,
  `extra="forbid"` everywhere) → `routers/` (HTTP) → `services/`
  (`xp`, `levels`, `quests`, `achievements`, `dashboard`, `activity`).
- Local-only: `HOST = "127.0.0.1"` (config), launch scripts bind 8001. No
  cloud, accounts, telemetry, broker, or market-data integration anywhere.

## P.2 Data model (15 tables)

`symbols`, `setups`, `emotions` (settings lists: name/sort_order/is_active —
soft-archival); `trades` (status open|closed, **label snapshots**
`symbol_label`/`setup_label` instead of FKs, manual `result`
win|loss|breakeven, `entry_price`/`exit_price` stored-only, optional manual
`user_pnl`, `screenshot_path` text-only, `deleted_at` soft delete);
`quick_reviews` (1:1 trade, followed_plan, execution_rating 1–5);
`deep_reviews` (1:1 trade, five sections + grade + takeaway); `lessons`
(source_type quick|deep|daily|weekly|emotional + source_id + trade_id);
`emotional_entries` (emotion snapshot, intensity 1–5, `occurred_at`,
denormalized `local_date` computed server-side); `daily_reviews`
(unique `review_date`); `weekly_reviews` (unique iso_year+iso_week);
`xp_events` (append-only ledger, **UNIQUE `idempotency_key`**);
`quest_progress` (quest_code unique, progress_current, completed_at,
**claimed_at** — added vs. Phase 1 sketch to support the explicit claim
workflow); `achievement_unlocks` (code PK, immutable, `seen_at`);
`ui_preferences`; `app_meta`.

## P.3 XP ledger & idempotency (implemented values)

| Activity | XP | Ledger key |
|---|---:|---|
| Trade creation | +20 | `capture:{trade_id}` |
| Quick Review | +15 | `qreview:{review_id}` |
| Deep Review | +30 | `dreview:{review_id}` |
| Lesson (≤3 per parent review) | +10 | `lesson:{lesson_id}` |
| First emotional entry / local day | +10 | `emotional:{local_date}` |
| Additional emotional entries / day | +2 | `emotional-entry:{entry_id}` |
| Daily Review | +15 | `daily:{date}` |
| Weekly Review | +30 | `weekly:{iso_year-week}` |
| Quest claim (tiers 25/50/75/100 where defined) | varies | `quest:{catalog_version}:{code}` |
| Close / edit / delete / P&L entry | **0** | — |

Activity insert + XP event + quest/achievement evaluation all commit in one
transaction (`flush`, then single `commit`; failure rolls back everything).
Amounts come only from `config.py` constants — no endpoint accepts an XP
amount. Total XP is always summed from the ledger. Edits/deletes never touch
the ledger (no clawback). Daily first-entry bonus is protected by the UNIQUE
constraint on the deterministic date key (concurrency backstop).

## P.4 Levels

Derived from ledger total; `xp_to_next(n) = 100 + 50(n−1)`; cumulative
thresholds 0/100/250/450/700/1000/1350/1750/2200/2700, formula continues
indefinitely. Titles 1–14 + mastery title for 15+. No level bonus XP; no
P&L/win-rate/frequency dependence.

## P.5 Quest catalog (23 quests)

FT-01…07, RF-01…04, JM-01…06, LQ-01 and LQ-03 implemented from persisted
counts. **RF-04 "Double Take"** (approved correction pass) uses the existing
`created_at`/`updated_at` timestamps: a review counts when it was updated
at least 7 days after creation (boundary inclusive; any review type —
quick/deep/daily/weekly; the edit itself awards NO XP). **LQ-03 "Mentor
Voice"** uses the nullable `weekly_reviews.advice_to_future_me` column
(added by the same approved pass, additive ALTER TABLE for existing v2
databases; historical NULL rows never count; blank advice normalises to
NULL). **LQ-02 is DEFERRED** — the Blueprint's keyword-matching wording
requires structured mistake tags (schema + product decision) and is NOT
faked with keyword matching. **CN-01…03 are
opt-in** (off by default; enabled via
`PUT /api/preferences/consistency_quests_enabled`) and their reward values
are **UNDECIDED** (`reward_xp = None`): they can complete but cannot be
claimed until the user decides values — no schema or ledger change will be
needed.

Claim workflow: evaluation (never awards XP) → `claimable` → explicit
`POST /api/quests/{code}/claim` → server validates completed ∧ unclaimed ∧
reward-decided → inserts ledger event + sets `claimed_at` atomically →
returns persisted state. Incomplete/duplicate/undecided claims → 409.
Quest reward tiers used: 25/50/75/100 (JM-03 uses 75 within the standard
tier ladder). Completion is latched (no punishment mechanics).

## P.6 Achievements

13 achievements across initiation/reflection/knowledge/curation/secret.
All conditions are persisted-count based. Secrets (`Night Shift`,
`The Phoenix`) masked as `???` until unlocked. Unlock rows are immutable;
only `seen_at` is settable. No P&L/risk/frequency conditions.

## P.7 Manual P&L

Optional `user_pnl` (float, accepts positive/negative/zero/null), set only
by explicit user input on create/update/close. Never computed from prices,
never converted, never used for XP/levels/quests/achievements. The dashboard
exposes an informational echo (`entries`, `sum`) only.

## P.8 API surface (v2, port 8001)

- `GET/POST /api/trades`, `GET/PATCH/DELETE /api/trades/{id}`
  (`?hard=` for hard delete), `POST /api/trades/{id}/close`,
  `GET /api/trades/{id}/screenshot` (resolved-path allow-list via
  `TRADEQUEST2_SCREENSHOT_DIRS` + extension/size checks; fails closed)
- `GET/POST /api/trades/{id}/quick-review`, `PATCH/DELETE /api/quick-reviews/{id}`
- `GET/POST /api/trades/{id}/deep-review`, `PATCH/DELETE /api/deep-reviews/{id}`
- `GET/POST /api/lessons`, `PATCH/DELETE /api/lessons/{id}`
- `GET/POST /api/emotional-entries`, `GET/PATCH/DELETE /api/emotional-entries/{id}`
- `GET/POST /api/daily-reviews[/{date}]`, `PATCH /api/daily-reviews/{date}`
- `GET/POST /api/weekly-reviews[/{YYYY-Www}]`, `PATCH /api/weekly-reviews/{week}`
- `GET/POST /api/settings/{symbols|setups|emotions}`,
  `PATCH/DELETE /api/settings/{list}/{id}` (`?hard=` refused while referenced),
  `GET/PUT /api/preferences[/{key}]`
- `GET /api/xp`, `GET /api/xp/events`, `GET /api/levels`
- `GET /api/quests`, `GET /api/quests/{code}`, `POST /api/quests/{code}/claim`
- `GET /api/achievements`, `POST /api/achievements/{code}/seen`
- `GET /api/dashboard`, `GET /api/system/health`, `GET /api/system/backup`,
  `GET /api/system/backups`

## P.9 Testing strategy

`backend/tests_v2/` (100 tests) + untouched v1 suite (79 tests) = 179 total,
all passing. Coverage: DB constraints/rollback/restart/historical-label
preservation; trade CRUD/close/PnL/zero-XP rules/screenshot safety; XP values,
idempotency, injection refusal, no-clawback; emotional daily +10/+2 with
midnight/timezone boundaries and race backstop; review/lesson cap; daily/
weekly one-per-period; level boundaries; quest claim workflow incl. duplicate,
concurrent, restart persistence, CN opt-in, deferred quests; achievement
unlock/immutability/hidden rules; dashboard honesty/empty states.

## P.10 Security & backup

127.0.0.1 binding, localhost-only CORS, `extra="forbid"` schemas, no client
XP input, append-only ledger, parameterized SQLAlchemy queries, screenshot
endpoint validates absolute-path + image-extension + size, `GET
/api/system/backup` creates a timestamped SQLite-consistent copy next to the
DB (last 10 kept). Full project backup (pre-Phase-2) at
`D:\trading strategy\TradeQuest_v1_backup_phase2`.

## P.11 Phase boundaries

Phase 2 = backend + docs only. No frontend redesign, no moving-car concept,
no Phase 3 work. The v1 frontend remains fully functional against the
untouched v1 backend.












