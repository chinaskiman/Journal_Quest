/** Shared API fixtures for tests - realistic backend response shapes. */
import type {
  Achievement,
  Dashboard,
  DashboardActivity,
  Quest,
  SettingItem,
  Trade,
  TradeList,
  XpSummary,
} from '../api/types'

export const setting = (id: number, name: string, is_active = true): SettingItem => ({
  id,
  name,
  sort_order: id,
  is_active,
  created_at: '2026-09-01T10:00:00',
  updated_at: '2026-09-01T10:00:00',
})

export const settingsList = (items: SettingItem[]) => ({ items })

export const trade = (id: number, overrides: Partial<Trade> = {}): Trade => ({
  id,
  status: 'closed',
  symbol_label: 'XAUUSD',
  setup_label: 'Breakout',
  direction: 'long',
  opened_at: '2026-09-28T09:30:00',
  closed_at: '2026-09-28T11:00:00',
  result: 'win',
  result_note: null,
  entry_price: 2650,
  exit_price: 2662,
  user_pnl: null,
  screenshot_path: null,
  thesis: null,
  notes: null,
  created_at: '2026-09-28T11:05:00',
  updated_at: '2026-09-28T11:05:00',
  ...overrides,
})

export const tradeList = (rows: Trade[]): TradeList => ({
  rows,
  total: rows.length,
  page: 1,
  page_size: 50,
})

export const quest = (code: string, overrides: Partial<Quest> = {}): Quest => ({
  code,
  name: `Quest ${code}`,
  category: 'milestone',
  description: `Description for ${code}`,
  target: 5,
  progress_current: 2,
  reward_xp: 50,
  opt_in: false,
  status: 'active',
  completed_at: null,
  claimed_at: null,
  claimable: false,
  ...overrides,
})

export const achievement = (code: string, overrides: Partial<Achievement> = {}): Achievement => ({
  code,
  name: `Achievement ${code}`,
  category: 'initiation',
  description: `Description ${code}`,
  hidden: false,
  unlocked: false,
  unlocked_at: null,
  seen_at: null,
  ...overrides,
})

export const emptyDashboard: Dashboard = {
  pilot: {
    total_xp: 0,
    level: 1,
    title: 'Initiate',
    current_level_xp: 0,
    next_level_xp_needed: 100,
    next_level_total_xp: 100,
    progress_pct: 0,
  },
  quests: { active: [], completed_count: 0, claimable_count: 0, claimed_count: 0 },
  achievements: { unlocked_count: 0 },
  journal: {
    trades_total: 0,
    open_trades: 0,
    closed_trades: 0,
    unreviewed_trade_ids: [],
    quick_reviews: 0,
    lessons: 0,
    emotional_entries: 0,
    daily_reviews: 0,
    daily_review_done_today: false,
    weekly_review_done_this_week: false,
  },
  manual_pnl_summary: { entries: 0, sum: 0 },
  recent_activity: [],
  streak: {
    enabled: true,
    baseline: '2026-10-01',
    current_streak: 0,
    min_days: 3,
    recovery_target: 2,
    active_event: null,
    message: null,
  },
}

// --- level progression fixtures -------------------------------------------------

/** Cumulative XP needed to REACH a level: 100 + 50*(n-1) per step (approved). */
export const cumulativeThreshold = (level: number): number => {
  let total = 0
  for (let n = 1; n < level; n += 1) total += 100 + 50 * (n - 1)
  return total
}

/**
 * Build the backend's `pilot` payload for a given XP total.
 *
 * Mirrors backend/app2/services/levels.py exactly so tests cannot hand-roll an
 * internally inconsistent payload (which is how the "XP to level" regression
 * stayed invisible):
 *   current_level_xp    = XP earned within the current level
 *   next_level_xp_needed= XP STILL needed to reach the next level (not the span)
 *   progress_pct        = current_level_xp / level span * 100
 */
export const pilotForXp = (
  totalXp: number,
  overrides: Partial<XpSummary> = {},
): XpSummary => {
  let level = 1
  while (cumulativeThreshold(level + 1) <= totalXp) level += 1
  const base = cumulativeThreshold(level)
  const span = 100 + 50 * (level - 1)
  const current = totalXp - base
  return {
    total_xp: totalXp,
    level,
    title: `Level ${level}`,
    current_level_xp: current,
    next_level_xp_needed: Math.max(0, base + span - totalXp),
    next_level_total_xp: base + span,
    progress_pct: Math.round(Math.min(100, (current / span) * 100) * 100) / 100,
    ...overrides,
  }
}

const activityEvent = (overrides: Partial<DashboardActivity> = {}): DashboardActivity => ({
  id: 1,
  event_type: 'quick_review',
  amount: 15,
  awarded_at: '2026-10-01T12:00:00',
  ...overrides,
})

/**
 * A *non-empty* dashboard at the given XP total.  The empty dashboard renders
 * the onboarding branch of the Quest Hub, which never shows the pilot panel -
 * tests of level display must use this builder instead.
 */
export const dashboardWithXp = (totalXp: number, pilotOverrides: Partial<XpSummary> = {}): Dashboard => ({
  ...emptyDashboard,
  pilot: pilotForXp(totalXp, pilotOverrides),
  quests: { active: [], completed_count: 1, claimable_count: 1, claimed_count: 1 },
  achievements: { unlocked_count: 3 },
  journal: {
    trades_total: 5,
    open_trades: 1,
    closed_trades: 4,
    unreviewed_trade_ids: [],
    quick_reviews: 3,
    lessons: 3,
    emotional_entries: 4,
    daily_reviews: 3,
    daily_review_done_today: true,
    weekly_review_done_this_week: true,
  },
  manual_pnl_summary: { entries: 4, sum: 355.25 },
  recent_activity: [
    activityEvent({ id: 1, event_type: 'trade_create', amount: 20 }),
    activityEvent({ id: 2, event_type: 'quick_review', amount: 15 }),
    activityEvent({ id: 3, event_type: 'quest', amount: 25, awarded_at: '2026-10-01T12:05:00' }),
  ],
})
