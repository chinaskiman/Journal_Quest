/**
 * TanStack Query hooks - the single server-state layer.
 *
 * "Optional resource" queries (a review for one trade/date/week) resolve a
 * backend 404 to `null` so pages can switch between create/edit modes without
 * treating "not written yet" as an error.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from './client'
import { invalidateJournal, invalidateProgression, qk } from './keys'
import type { SettingListName } from './types'

async function or404<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

// --- system / dashboard ---
export function useDashboard() {
  return useQuery({ queryKey: qk.dashboard, queryFn: api.dashboard })
}

export function useXpSummary() {
  return useQuery({ queryKey: qk.xp, queryFn: api.getXpSummary })
}

// --- gamification ---
export function useQuests() {
  return useQuery({ queryKey: qk.quests, queryFn: api.listQuests })
}

export function useAchievements() {
  return useQuery({ queryKey: qk.achievements, queryFn: api.listAchievements })
}

// --- trades ---
export function useTrades(filters: { status?: string; symbol?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: qk.trades(filters),
    queryFn: () => api.listTrades(filters),
    placeholderData: (prev) => prev,
  })
}

export function useTrade(id: number) {
  return useQuery({ queryKey: qk.trade(id), queryFn: () => api.getTrade(id), enabled: id > 0 })
}

// --- reviews ---
export function useQuickReview(tradeId: number) {
  return useQuery({
    queryKey: qk.quickReview(tradeId),
    queryFn: () => or404(api.getQuickReview(tradeId)),
    enabled: tradeId > 0,
  })
}

export function useDeepReview(tradeId: number) {
  return useQuery({
    queryKey: qk.deepReview(tradeId),
    queryFn: () => or404(api.getDeepReview(tradeId)),
    enabled: tradeId > 0,
  })
}

export function useLessons(params: { source_type?: string; trade_id?: number }) {
  return useQuery({ queryKey: qk.lessons(params), queryFn: () => api.listLessons(params) })
}

// --- emotional journal ---
export function useEmotionalEntries(params: { trade_id?: number; page?: number } = {}) {
  return useQuery({
    queryKey: qk.emotional(params),
    queryFn: () => api.listEmotionalEntries(params),
    placeholderData: (prev) => prev,
  })
}

// --- daily / weekly reviews ---
export function useDailyReview(date: string) {
  return useQuery({
    queryKey: qk.dailyReview(date),
    queryFn: () => or404(api.getDailyReview(date)),
    enabled: Boolean(date),
  })
}

export function useDailyReviews(page = 1) {
  return useQuery({ queryKey: qk.dailyReviews(page), queryFn: () => api.listDailyReviews(page) })
}

export function useWeeklyReview(week: string) {
  return useQuery({
    queryKey: qk.weeklyReview(week),
    queryFn: () => or404(api.getWeeklyReview(week)),
    enabled: Boolean(week),
  })
}

export function useWeeklyReviews(page = 1) {
  return useQuery({ queryKey: qk.weeklyReviews(page), queryFn: () => api.listWeeklyReviews(page) })
}

// --- settings / preferences ---
export function useSettings(list: SettingListName, includeInactive = false) {
  return useQuery({
    queryKey: qk.settings(list, includeInactive),
    queryFn: () => api.listSettings(list, includeInactive),
  })
}

export function usePreferences() {
  return useQuery({ queryKey: qk.preferences, queryFn: api.getPreferences })
}

/** Expose the client for mutation success handlers (invalidation). */
export function useInvalidation() {
  const client = useQueryClient()
  return {
    progress: () => invalidateProgression(client),
    journal: () => invalidateJournal(client),
  }
}
