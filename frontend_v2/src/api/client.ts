/**
 * Centralized typed API client for the LOCAL v2 backend.
 *
 * Same-origin in both workflows: the Vite dev server proxies /api to
 * 127.0.0.1:8001, and the production build is served by the backend itself.
 * No XP/level/quest logic lives here - responses are returned verbatim.
 */
import type {
  AchievementList,
  ClaimResult,
  DailyReview,
  DailyReviewInput,
  DailyReviewMutation,
  DeepReview,
  DeepReviewInput,
  DeepReviewMutation,
  EmotionalEntry,
  EmotionalEntryInput,
  EmotionalEntryMutation,
  EmotionalList,
  Lesson,
  LessonMutation,
  Preferences,
  QuestList,
  QuickReview,
  QuickReviewInput,
  QuickReviewMutation,
  SettingItem,
  SettingList,
  SettingListName,
  Trade,
  TradeCreateInput,
  TradeList,
  TradeMutation,
  TradeUpdateInput,
  WeeklyReview,
  WeeklyReviewInput,
  WeeklyReviewMutation,
  XpEventList,
  XpSummary,
  Dashboard,
  StreakEvent,
  StreakReflectionInput,
  StreakState,
} from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail))
        detail = (body.detail as { msg?: string }[]).map((d) => d.msg).join('; ')
    } catch {
      /* non-JSON error body - keep the status text */
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  // --- system ---
  health: () => request<{ status: string; app: string; host: string }>('/api/system/health'),
  dashboard: () => request<Dashboard>('/api/dashboard'),
  createBackup: () =>
    request<{ backup: string; kept: number }>('/api/system/backup'),
  listBackups: () => request<{ items: string[] }>('/api/system/backups'),

  // --- streak break & recovery ---
  // Read-only view of the current streak and recovery lifecycle.
  getStreak: () => request<StreakState>('/api/streak'),
  // Idempotent: dismisses the Quest Hub alert for the current event.
  markStreakAlertSeen: () =>
    request<StreakEvent>('/api/streak/alert-seen', { method: 'POST' }),
  // Idempotent: one reflection per streak event; re-saving updates it.
  saveStreakReflection: (payload: StreakReflectionInput) =>
    request<StreakEvent>('/api/streak/reflection', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  // --- trades ---
  listTrades: (opts: { status?: string; symbol?: string; page?: number; page_size?: number } = {}) =>
    request<TradeList>(`/api/trades${query({ ...opts })}`),
  getTrade: (id: number) => request<Trade>(`/api/trades/${id}`),
  createTrade: (payload: TradeCreateInput) =>
    request<TradeMutation>('/api/trades', { method: 'POST', body: JSON.stringify(payload) }),
  updateTrade: (id: number, payload: TradeUpdateInput) =>
    request<Trade>(`/api/trades/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  closeTrade: (
    id: number,
    payload: {
      closed_at?: string | null
      exit_price?: number | null
      user_pnl?: number | null
      result?: string | null
      result_note?: string | null
    },
  ) => request<Trade>(`/api/trades/${id}/close`, { method: 'POST', body: JSON.stringify(payload) }),
  deleteTrade: (id: number, hard = false) =>
    request<void>(`/api/trades/${id}${query({ hard })}`, { method: 'DELETE' }),
  screenshotUrl: (id: number) => `/api/trades/${id}/screenshot`,

  // --- quick review ---
  getQuickReview: (tradeId: number) => request<QuickReview>(`/api/trades/${tradeId}/quick-review`),
  createQuickReview: (tradeId: number, payload: QuickReviewInput) =>
    request<QuickReviewMutation>(`/api/trades/${tradeId}/quick-review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateQuickReview: (reviewId: number, payload: QuickReviewInput) =>
    request<QuickReview>(`/api/quick-reviews/${reviewId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // --- deep review + lessons ---
  getDeepReview: (tradeId: number) => request<DeepReview>(`/api/trades/${tradeId}/deep-review`),
  createDeepReview: (tradeId: number, payload: DeepReviewInput) =>
    request<DeepReviewMutation>(`/api/trades/${tradeId}/deep-review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateDeepReview: (reviewId: number, payload: DeepReviewInput) =>
    request<DeepReview>(`/api/deep-reviews/${reviewId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  listLessons: (
    opts: { source_type?: string; trade_id?: number; page?: number; page_size?: number } = {},
  ) =>
    request<{ rows: Lesson[]; total: number; page: number; page_size: number }>(
      `/api/lessons${query({ ...opts })}`,
    ),
  createLesson: (payload: {
    source_type: string
    source_id?: number | null
    trade_id?: number | null
    text: string
  }) =>
    request<LessonMutation>('/api/lessons', { method: 'POST', body: JSON.stringify(payload) }),
  updateLesson: (id: number, text: string) =>
    request<Lesson>(`/api/lessons/${id}`, { method: 'PATCH', body: JSON.stringify({ text }) }),
  deleteLesson: (id: number) => request<void>(`/api/lessons/${id}`, { method: 'DELETE' }),

  // --- emotional journal ---
  listEmotionalEntries: (
    opts: { trade_id?: number; local_date?: string; page?: number; page_size?: number } = {},
  ) => request<EmotionalList>(`/api/emotional-entries${query({ ...opts })}`),
  createEmotionalEntry: (payload: EmotionalEntryInput) =>
    request<EmotionalEntryMutation>('/api/emotional-entries', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getEmotionalEntry: (id: number) => request<EmotionalEntry>(`/api/emotional-entries/${id}`),
  updateEmotionalEntry: (id: number, payload: Partial<EmotionalEntryInput>) =>
    request<EmotionalEntry>(`/api/emotional-entries/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteEmotionalEntry: (id: number) =>
    request<void>(`/api/emotional-entries/${id}`, { method: 'DELETE' }),

  // --- daily reviews ---
  listDailyReviews: (page = 1) =>
    request<{ rows: DailyReview[]; total: number; page: number; page_size: number }>(
      `/api/daily-reviews${query({ page })}`,
    ),
  getDailyReview: (date: string) => request<DailyReview>(`/api/daily-reviews/${date}`),
  createDailyReview: (date: string, payload: DailyReviewInput) =>
    request<DailyReviewMutation>(`/api/daily-reviews/${date}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateDailyReview: (date: string, payload: DailyReviewInput) =>
    request<DailyReview>(`/api/daily-reviews/${date}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // --- weekly reviews ---
  listWeeklyReviews: (page = 1) =>
    request<{ rows: WeeklyReview[]; total: number; page: number; page_size: number }>(
      `/api/weekly-reviews${query({ page })}`,
    ),
  getWeeklyReview: (week: string) => request<WeeklyReview>(`/api/weekly-reviews/${week}`),
  createWeeklyReview: (week: string, payload: WeeklyReviewInput) =>
    request<WeeklyReviewMutation>(`/api/weekly-reviews/${week}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateWeeklyReview: (week: string, payload: WeeklyReviewInput) =>
    request<WeeklyReview>(`/api/weekly-reviews/${week}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // --- gamification (read-only + explicit claim/seen) ---
  getXpSummary: () => request<XpSummary>('/api/xp'),
  listXpEvents: (page = 1) => request<XpEventList>(`/api/xp/events${query({ page })}`),
  listQuests: () => request<QuestList>('/api/quests'),
  claimQuest: (code: string) =>
    request<ClaimResult>(`/api/quests/${code}/claim`, { method: 'POST' }),
  listAchievements: () => request<AchievementList>('/api/achievements'),
  markAchievementSeen: (code: string) =>
    request<void>(`/api/achievements/${code}/seen`, { method: 'POST' }),

  // --- settings + preferences ---
  listSettings: (list: SettingListName, includeInactive = false) =>
    request<SettingList>(`/api/settings/${list}${query({ include_inactive: includeInactive })}`),
  createSetting: (list: SettingListName, name: string) =>
    request<SettingItem>(`/api/settings/${list}`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  updateSetting: (
    list: SettingListName,
    id: number,
    payload: { name?: string; is_active?: boolean },
  ) =>
    request<SettingItem>(`/api/settings/${list}/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteSetting: (list: SettingListName, id: number, hard = false) =>
    request<void>(`/api/settings/${list}/${id}${query({ hard })}`, { method: 'DELETE' }),
  getPreferences: () => request<Preferences>('/api/preferences'),
  putPreference: (key: string, value: unknown) =>
    request<{ key: string; stored: boolean }>(`/api/preferences/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ value: JSON.stringify(value) }),
    }),
}
