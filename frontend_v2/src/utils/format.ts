/** Formatting helpers - presentation only, never progression math. */

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return Number.isInteger(value) ? String(value) : value.toFixed(digits)
}

/** Local ISO date (YYYY-MM-DD) for <input type="date"> defaults. */
export function todayIso(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** Local date-time (YYYY-MM-DDTHH:mm) for <input type="datetime-local">. */
export function nowDateTimeLocal(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${todayIso()}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Current ISO week as "YYYY-Www" (the backend's weekly-review key format). */
export function currentIsoWeek(): string {
  const d = new Date()
  // ISO week algorithm (Monday start)
  const target = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const dayNr = (target.getUTCDay() + 6) % 7
  target.setUTCDate(target.getUTCDate() - dayNr + 3)
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4))
  const firstDayNr = (firstThursday.getUTCDay() + 6) % 7
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNr + 3)
  const week = 1 + Math.round((target.getTime() - firstThursday.getTime()) / (7 * 86400000))
  return `${target.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}

export function isoWeekLabel(week: string): string {
  const m = /^(\d{4})-W(\d{2})$/.exec(week)
  if (!m) return week
  return `Week ${Number(m[2])}, ${m[1]}`
}

/** Friendly labels for backend XP event types (display only). */
export const EVENT_LABELS: Record<string, string> = {
  trade_create: 'Trade captured',
  quick_review: 'Quick Review',
  deep_review: 'Deep Review',
  lesson: 'Lesson recorded',
  emotional_first: 'Emotional Journal (first of day)',
  emotional_additional: 'Emotional Journal (additional)',
  daily_review: 'Daily Review',
  weekly_review: 'Weekly Review',
  quest: 'Quest reward',
}

export function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType.replace(/_/g, ' ')
}
