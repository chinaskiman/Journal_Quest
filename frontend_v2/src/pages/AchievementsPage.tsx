/**
 * Achievements gallery - grouped by the categories the backend implements.
 * Hidden secret achievements show only "???" / "Hidden achievement." until the
 * backend reports them unlocked; nothing is invented locally.
 */
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAchievements, useInvalidation } from '../api/hooks'
import { useToast } from '../feedback/ToastContext'
import { formatDate } from '../utils/format'
import { Panel } from '../components/ui'
import { ErrorState, LoadingState } from '../components/states'
import { Award, Lock } from 'lucide-react'

const CATEGORY_LABELS: Record<string, string> = {
  initiation: 'Initiation',
  reflection: 'Reflection',
  knowledge: 'Knowledge',
  curation: 'Curation',
  secret: 'Secret',
}

export default function AchievementsPage() {
  const toast = useToast()
  const achievements = useAchievements()
  const invalidate = useInvalidation()

  const seenMutation = useMutation({
    mutationFn: (code: string) => api.markAchievementSeen(code),
    onSuccess: () => {
      invalidate.progress()
    },
    onError: () => {
      // Non-critical marker - keep quiet rather than alarming.
      void toast
    },
  })

  if (achievements.isPending) return <LoadingState label="Loading achievements…" />
  if (achievements.isError)
    return <ErrorState message={achievements.error.message} onRetry={() => void achievements.refetch()} />

  const items = achievements.data.items
  const unlocked = items.filter((a) => a.unlocked)
  const groups = new Map<string, typeof items>()
  for (const item of items) {
    const list = groups.get(item.category) ?? []
    list.push(item)
    groups.set(item.category, list)
  }

  return (
    <>
      <div className="topbar">
        <h1>Achievements</h1>
        <span className="faint">
          {unlocked.length} of {items.length} unlocked
        </span>
      </div>

      <p className="muted">
        Achievements recognize journaling habits — not trading outcomes. They
        are awarded automatically by the server when their conditions are met.
      </p>

      {[...groups.entries()].map(([category, group]) => (
        <Panel key={category} title={CATEGORY_LABELS[category] ?? category} accent>
          <div className="ach-grid">
            {group.map((a) => (
              <div
                key={a.code}
                className={`ach-card ${a.unlocked ? 'unlocked' : 'locked'}`}
                aria-label={a.unlocked ? `${a.name} (unlocked)` : 'Locked achievement'}
              >
                <div className="row spread">
                  <span className="ach-icon" aria-hidden>
                    {a.unlocked ? <Award size={18} /> : <Lock size={18} />}
                  </span>
                  {a.unlocked && a.seen_at === null && (
                    <span className="badge badge-gold">New</span>
                  )}
                </div>
                <strong>{a.unlocked ? a.name : '???'}</strong>
                <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                  {a.unlocked ? a.description : 'Hidden achievement.'}
                </p>
                {a.unlocked && a.unlocked_at && (
                  <p className="faint" style={{ margin: 0 }}>
                    Unlocked {formatDate(a.unlocked_at.slice(0, 10))}
                  </p>
                )}
                {a.unlocked && a.seen_at === null && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => seenMutation.mutate(a.code)}
                    disabled={seenMutation.isPending}
                  >
                    Mark as seen
                  </button>
                )}
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </>
  )
}
