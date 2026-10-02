/**
 * Typed API contract for the Trade Quest v2 backend.
 *
 * Every interface mirrors a Pydantic schema in backend/app2/schemas.py exactly.
 * XP, level, quest-progress and achievement state are ALWAYS read from the
 * backend; nothing here computes progression locally.
 */

// --- shared mutation feedback (backend/app2/schemas.py, "mutation feedback") ---

export interface LevelUp {
  level: number
  title: string
}

export interface MutationFeedback {
  /** XP the ledger actually inserted for this operation (0 on capped/idempotent). */
  xp_awarded: number
  /** Non-null only when this mutation crossed a level threshold. */
  level_up: LevelUp | null
}

// --- settings -----------------------------------------------------------------

export interface SettingItem {
  id: number
  name: string
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SettingList {
  items: SettingItem[]
}

export type SettingListName = 'symbols' | 'setups' | 'emotions'

// --- trades ---------------------------------------------------------------------

export type TradeStatus = 'open' | 'closed'
export type TradeResult = 'win' | 'loss' | 'breakeven'

export interface Trade {
  id: number
  status: TradeStatus
  symbol_label: string
  setup_label: string | null
  direction: 'long' | 'short' | null
  opened_at: string
  closed_at: string | null
  result: TradeResult | null
  result_note: string | null
  entry_price: number | null
  exit_price: number | null
  user_pnl: number | null
  screenshot_path: string | null
  thesis: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface TradeList {
  rows: Trade[]
  total: number
  page: number
  page_size: number
}

export interface TradeMutation extends Trade, MutationFeedback {}

export interface TradeCreateInput {
  symbol: string
  setup?: string | null
  direction?: 'long' | 'short' | null
  opened_at: string
  entry_price?: number | null
  screenshot_path?: string | null
  thesis?: string | null
  notes?: string | null
  user_pnl?: number | null
  status?: TradeStatus
  closed_at?: string | null
  result?: TradeResult | null
  result_note?: string | null
  exit_price?: number | null
}

export interface TradeUpdateInput extends Partial<TradeCreateInput> {}

// --- quick review -----------------------------------------------------------------

export interface QuickReview {
  id: number
  trade_id: number
  followed_plan: 'yes' | 'partly' | 'no' | null
  execution_rating: number
  went_well: string | null
  went_wrong: string | null
  improve: string | null
  created_at: string
  updated_at: string
}

export interface QuickReviewMutation extends QuickReview, MutationFeedback {}

export interface QuickReviewInput {
  followed_plan?: 'yes' | 'partly' | 'no' | null
  execution_rating: number
  went_well?: string | null
  went_wrong?: string | null
  improve?: string | null
}

// --- deep review + lessons ----------------------------------------------------------

export interface Lesson {
  id: number
  source_type: 'quick' | 'deep' | 'daily' | 'weekly' | 'emotional'
  source_id: number | null
  trade_id: number | null
  text: string
  created_at: string
  updated_at: string
}

export interface LessonMutation extends Lesson, MutationFeedback {}

export interface DeepReview {
  id: number
  trade_id: number
  plan_review: string | null
  execution_review: string | null
  risk_review: string | null
  emotions_review: string | null
  mistakes: string | null
  grade: 'A' | 'B' | 'C' | 'D' | 'F' | null
  key_takeaway: string | null
  created_at: string
  updated_at: string
  lessons: Lesson[]
}

export interface DeepReviewMutation extends DeepReview, MutationFeedback {}

export interface DeepReviewInput {
  plan_review?: string | null
  execution_review?: string | null
  risk_review?: string | null
  emotions_review?: string | null
  mistakes?: string | null
  grade?: 'A' | 'B' | 'C' | 'D' | 'F' | null
  key_takeaway?: string | null
  lessons?: { text: string }[]
}

// --- emotional journal ---------------------------------------------------------------

export interface EmotionalEntry {
  id: number
  trade_id: number | null
  occurred_at: string
  local_date: string
  emotion_label: string
  intensity: number
  trigger: string | null
  body: string | null
  created_at: string
  updated_at: string
}

export interface EmotionalEntryMutation extends EmotionalEntry, MutationFeedback {}

export interface EmotionalEntryInput {
  emotion: string
  intensity: number
  trade_id?: number | null
  occurred_at?: string | null
  trigger?: string | null
  body?: string | null
}

export interface EmotionalList {
  rows: EmotionalEntry[]
  total: number
}

// --- daily / weekly reviews -------------------------------------------------------------

export interface DailyReview {
  id: number
  review_date: string
  energy: number | null
  focus: number | null
  mood: number | null
  reflection: string | null
  created_at: string
  updated_at: string
}

export interface DailyReviewMutation extends DailyReview, MutationFeedback {}

export interface DailyReviewInput {
  energy?: number | null
  focus?: number | null
  mood?: number | null
  reflection?: string | null
}

export interface WeeklyReview {
  id: number
  iso_year: number
  iso_week: number
  highlights: string | null
  challenges: string | null
  patterns: string | null
  plan_next_week: string | null
  advice_to_future_me: string | null
  created_at: string
  updated_at: string
}

export interface WeeklyReviewMutation extends WeeklyReview, MutationFeedback {}

export interface WeeklyReviewInput {
  highlights?: string | null
  challenges?: string | null
  patterns?: string | null
  plan_next_week?: string | null
  advice_to_future_me?: string | null
}

// --- gamification ------------------------------------------------------------------------

export interface XpSummary {
  total_xp: number
  level: number
  title: string
  current_level_xp: number
  next_level_xp_needed: number
  next_level_total_xp: number | null
  progress_pct: number
}

export interface XpEvent {
  id: number
  event_type: string
  amount: number
  idempotency_key: string
  entity_type: string | null
  entity_id: number | null
  awarded_at: string
}

export interface XpEventList {
  rows: XpEvent[]
  total: number
  page: number
  page_size: number
}

export interface Quest {
  code: string
  name: string
  category: string
  description: string
  target: number
  progress_current: number
  reward_xp: number | null // null => undecided (Consistency quests)
  opt_in: boolean
  status: 'active' | 'deferred'
  completed_at: string | null
  claimed_at: string | null
  claimable: boolean
}

export interface QuestList {
  items: Quest[]
}

export interface ClaimResult {
  awarded_xp: number
  level_up: LevelUp | null
  quest: Quest
}

export interface Achievement {
  code: string
  name: string // "???" while hidden AND locked
  category: string
  description: string // "Hidden achievement." while hidden AND locked
  hidden: boolean
  unlocked: boolean
  unlocked_at: string | null
  seen_at: string | null
}

export interface AchievementList {
  items: Achievement[]
}

// --- dashboard / system ---------------------------------------------------------------------

export interface DashboardActivity {
  id: number
  event_type: string
  amount: number
  awarded_at: string | null
}

export interface Dashboard {
  pilot: XpSummary
  quests: {
    active: Quest[]
    completed_count: number
    claimable_count: number
    claimed_count: number
  }
  achievements: { unlocked_count: number }
  journal: {
    trades_total: number
    open_trades: number
    closed_trades: number
    unreviewed_trade_ids: number[]
    quick_reviews: number
    lessons: number
    emotional_entries: number
    daily_reviews: number
    daily_review_done_today: boolean
    weekly_review_done_this_week: boolean
  }
  manual_pnl_summary: { entries: number; sum: number }
  recent_activity: DashboardActivity[]
  streak: StreakState
}

/* --- Streak Break & Recovery --------------------------------------------- */

export type StreakStage =
  | 'detected'
  | 'reflection_done'
  | 'recovery_done'
  | 'badge_unlocked'

export interface StreakReflection {
  obstacle: string | null
  resume_step: string | null
}

export interface StreakEvent {
  id: number
  broke_on: string
  detected_on: string
  streak_length: number
  stage: StreakStage
  reflection_done: boolean
  recovery_target: number
  recovery_current: number
  recovery_done: boolean
  recovery_days: string[]
  alert_seen_at: string | null
  reflection: StreakReflection | null
  as_of: string
}

export interface StreakState {
  enabled: boolean
  baseline: string | null
  current_streak: number
  min_days: number
  recovery_target: number
  active_event: StreakEvent | null
  message: string | null
}

export interface StreakReflectionInput {
  obstacle?: string | null
  resume_step?: string | null
}

export interface Preferences {
  items: Record<string, unknown>
}
