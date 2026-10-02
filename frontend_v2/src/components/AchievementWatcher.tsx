/**
 * Watches the achievements query and raises a restrained notification when a
 * NEW unlock appears between fetches (never on the initial load, never twice
 * for the same unlock - guarded by the previously observed snapshot).
 */
import { useEffect, useRef } from 'react'
import { useAchievements } from '../api/hooks'
import { useToast } from '../feedback/ToastContext'

export function AchievementWatcher() {
  const toast = useToast()
  const achievements = useAchievements()
  const knownCodes = useRef<Set<string> | null>(null)

  useEffect(() => {
    if (!achievements.data) return
    const unlocked = achievements.data.items.filter((a) => a.unlocked)
    const unlockedCodes = new Set(unlocked.map((a) => a.code))
    if (knownCodes.current === null) {
      // Baseline: the first snapshot is never celebrated (page reloads would
      // otherwise re-notify old unlocks).
      knownCodes.current = unlockedCodes
      return
    }
    for (const item of unlocked) {
      if (!knownCodes.current.has(item.code)) {
        toast.achievement(item.name)
      }
    }
    knownCodes.current = unlockedCodes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [achievements.data])

  return null
}
