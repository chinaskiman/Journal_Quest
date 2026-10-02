import type { QueryClient } from '@tanstack/react-query'

/** Central query-key registry. */
export const qk = {
  health: ['health'] as const,
  dashboard: ['dashboard'] as const,
  xp: ['xp'] as const,
  xpEvents: (page: number) => ['xp-events', page] as const,
  quests: ['quests'] as const,
  achievements: ['achievements'] as const,
  trades: (filters: Record<string, unknown>) => ['trades', filters] as const,
  trade: (id: number) => ['trade', id] as const,
  quickReview: (tradeId: number) => ['quick-review', tradeId] as const,
  deepReview: (tradeId: number) => ['deep-review', tradeId] as const,
  lessons: (params: Record<string, unknown>) => ['lessons', params] as const,
  emotional: (params: Record<string, unknown>) => ['emotional', params] as const,
  emotionalEntry: (id: number) => ['emotional-entry', id] as const,
  dailyReviews: (page: number) => ['daily-reviews', page] as const,
  dailyReview: (date: string) => ['daily-review', date] as const,
  weeklyReviews: (page: number) => ['weekly-reviews', page] as const,
  weeklyReview: (week: string) => ['weekly-review', week] as const,
  settings: (list: string, includeInactive: boolean) => ['settings', list, includeInactive] as const,
  preferences: ['preferences'] as const,
}

/**
 * Invalidate everything that changes when an XP-awarding mutation succeeds.
 * Called ONLY from mutation success handlers (never on refetch), so query
 * refreshes can never duplicate notifications.
 */
export function invalidateProgression(client: QueryClient) {
  void client.invalidateQueries({ queryKey: qk.dashboard })
  void client.invalidateQueries({ queryKey: qk.xp })
  void client.invalidateQueries({ queryKey: ['xp-events'] })
  void client.invalidateQueries({ queryKey: qk.quests })
  void client.invalidateQueries({ queryKey: qk.achievements })
}

/** Journal record lists (no progression change, but lists must refresh). */
export function invalidateJournal(client: QueryClient) {
  invalidateProgression(client)
  void client.invalidateQueries({ queryKey: ['trades'] })
  void client.invalidateQueries({ queryKey: ['lessons'] })
  void client.invalidateQueries({ queryKey: ['emotional'] })
  void client.invalidateQueries({ queryKey: ['daily-review'] })
  void client.invalidateQueries({ queryKey: ['daily-reviews'] })
  void client.invalidateQueries({ queryKey: ['weekly-review'] })
  void client.invalidateQueries({ queryKey: ['weekly-reviews'] })
  void client.invalidateQueries({ queryKey: ['quick-review'] })
  void client.invalidateQueries({ queryKey: ['deep-review'] })
}
