import { CheckCircle2, Clock, Gift, HelpCircle, Lock } from 'lucide-react'
import type { Quest } from '../api/types'
import { ProgressBar } from './ui'

export const QUEST_CATEGORY_LABELS: Record<string, string> = {
  first_time: 'First Steps',
  reflection: 'Reflection',
  milestone: 'Journal Milestones',
  consistency: 'Consistency',
  learning: 'Learning',
}

export function QuestCard({
  quest,
  onClaim,
  claimPending,
}: {
  quest: Quest
  onClaim?: (code: string) => void
  claimPending?: boolean
}) {
  const completed = quest.completed_at !== null
  const claimed = quest.claimed_at !== null

  return (
    <article className={`quest-card${completed ? ' completed' : ''}`} aria-label={quest.name}>
      <div className="quest-card-head">
        <span className="quest-name">{quest.name}</span>
        <span className="badge badge-muted">{QUEST_CATEGORY_LABELS[quest.category] ?? quest.category}</span>
      </div>
      <p className="quest-desc">{quest.description}</p>
      <ProgressBar
        value={quest.progress_current}
        max={quest.target}
        gold={completed}
        label={`${quest.name} progress`}
      />
      <div className="row spread">
        <span className="quest-meta num">
          {quest.progress_current} / {quest.target}
        </span>
        <span className="row" style={{ gap: '0.4rem' }}>
          {quest.reward_xp !== null ? (
            <span className="badge badge-gold">
              <Gift size={12} aria-hidden /> {quest.reward_xp} XP
            </span>
          ) : (
            <span className="badge badge-muted">
              <HelpCircle size={12} aria-hidden /> Reward undecided
            </span>
          )}
          {quest.status === 'deferred' && (
            <span className="badge badge-muted">
              <Clock size={12} aria-hidden /> Not yet available
            </span>
          )}
          {claimed && (
            <span className="badge badge-success">
              <CheckCircle2 size={12} aria-hidden /> Claimed
            </span>
          )}
          {completed && !claimed && quest.reward_xp === null && quest.status === 'active' && (
            <span className="badge badge-cyan">
              <Lock size={12} aria-hidden /> Awaiting reward decision
            </span>
          )}
        </span>
      </div>
      {quest.claimable && onClaim && (
        <button
          type="button"
          className="btn btn-gold"
          onClick={() => onClaim(quest.code)}
          disabled={claimPending}
        >
          <Gift size={15} aria-hidden /> {claimPending ? 'Claiming…' : 'Claim reward'}
        </button>
      )}
    </article>
  )
}
