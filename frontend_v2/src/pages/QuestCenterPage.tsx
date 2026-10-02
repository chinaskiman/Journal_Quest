/**
 * Quest Center - all quest states from the backend with the explicit Claim
 * workflow.  XP is awarded ONLY through the backend claim endpoint; the UI
 * shows rewards the backend defines and "Reward undecided" for null rewards.
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { useInvalidation, usePreferences, useQuests } from '../api/hooks'
import { useToast } from '../feedback/ToastContext'
import { Panel } from '../components/ui'
import { ErrorState, LoadingState } from '../components/states'
import { QuestCard } from '../components/QuestCard'

const CONSISTENCY_KEY = 'consistency_quests_enabled'

export default function QuestCenterPage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const quests = useQuests()
  const preferences = usePreferences()
  const [claimingCode, setClaimingCode] = useState<string | null>(null)

  const consistencyEnabled = preferences.data?.items[CONSISTENCY_KEY] === true

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => api.putPreference(CONSISTENCY_KEY, enabled),
    onSuccess: () => {
      invalidate.journal()
    },
    onError: (error) => toast.error(error.message),
  })

  const claimMutation = useMutation({
    mutationFn: (code: string) => api.claimQuest(code),
    onSuccess: (result) => {
      // ClaimResult uses awarded_xp (not xp_awarded) - map into the feedback.
      toast.feedback(
        { xp_awarded: result.awarded_xp, level_up: result.level_up },
        `Quest reward — ${result.quest.name}`,
      )
      invalidate.journal()
      setClaimingCode(null)
    },
    onError: (error) => {
      // already-claimed / incomplete / disabled / undecided - clear, honest note.
      toast.error(error.message)
      setClaimingCode(null)
    },
  })

  if (quests.isPending) return <LoadingState label="Evaluating quests…" />
  if (quests.isError) return <ErrorState message={quests.error.message} onRetry={() => void quests.refetch()} />

  const items = quests.data.items
  const claimable = items.filter((q) => q.claimable)
  const inProgress = items.filter(
    (q) => !q.completed_at && q.status === 'active' && (!q.opt_in || consistencyEnabled),
  )
  const claimed = items.filter((q) => q.claimed_at !== null)
  const deferred = items.filter((q) => q.status === 'deferred')
  const optInDisabled = items.filter((q) => q.opt_in && !consistencyEnabled)

  return (
    <>
      <div className="topbar">
        <h1>Quest Center</h1>
      </div>

      {claimable.length > 0 && (
        <Panel title="Ready to claim" accent>
          <div className="grid-2">
            {claimable.map((quest) => (
              <QuestCard
                key={quest.code}
                quest={quest}
                onClaim={(code) => {
                  setClaimingCode(code)
                  claimMutation.mutate(code)
                }}
                claimPending={claimingCode === quest.code && claimMutation.isPending}
              />
            ))}
          </div>
        </Panel>
      )}

      <Panel
        title="In progress"
        accent
        actions={<span className="faint">{inProgress.length} active</span>}
      >
        {inProgress.length === 0 ? (
          <p className="muted">No quests in progress right now.</p>
        ) : (
          <div className="grid-2">
            {inProgress.map((quest) => (
              <QuestCard key={quest.code} quest={quest} />
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Completed & claimed"
        actions={<span className="faint">{claimed.length} claimed</span>}
      >
        {claimed.length === 0 ? (
          <p className="muted">Claimed quests will be listed here.</p>
        ) : (
          <div className="grid-2">
            {claimed.map((quest) => (
              <QuestCard key={quest.code} quest={quest} />
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Consistency quests (opt-in)">
        <p className="muted">
          Consistency quests are optional and stay disabled until you enable
          them. They simply count your journaling streaks; enabling or
          disabling them has no penalties and no streak-loss warnings.
          Their rewards are not decided yet, so none are displayed.
        </p>
        {optInDisabled.length > 0 && (
          <div className="grid-2">
            {optInDisabled.map((quest) => (
              <QuestCard key={quest.code} quest={quest} />
            ))}
          </div>
        )}
        <div className="form-actions">
          <button
            type="button"
            className="btn"
            aria-pressed={consistencyEnabled}
            onClick={() => toggleMutation.mutate(!consistencyEnabled)}
            disabled={toggleMutation.isPending || preferences.isPending}
          >
            {toggleMutation.isPending
              ? 'Saving…'
              : consistencyEnabled
                ? 'Disable consistency quests'
                : 'Enable consistency quests'}
          </button>
          <span className="faint">
            {consistencyEnabled ? 'Currently enabled' : 'Currently disabled'}
          </span>
        </div>
      </Panel>

      {deferred.length > 0 && (
        <Panel title="Not yet available">
          <p className="muted">
            These quests are deferred by design and cannot be progressed or
            claimed yet.
          </p>
          <div className="grid-2">
            {deferred.map((quest) => (
              <QuestCard key={quest.code} quest={quest} />
            ))}
          </div>
        </Panel>
      )}
    </>
  )
}
