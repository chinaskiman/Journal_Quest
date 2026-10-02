/**
 * Quest Hub - mission-control landing page.  Every value comes from
 * /api/dashboard, /api/quests and /api/achievements - nothing is computed,
 * simulated or invented locally.  A fresh database shows an honest onboarding
 * empty state.
 */
import { useQueries, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAchievements, useDashboard, useQuests } from '../api/hooks'
import { eventLabel, formatDateTime } from '../utils/format'
import { Panel, ProgressBar, StatTile } from '../components/ui'
import { ErrorState, LoadingState } from '../components/states'
import { QuestCard } from '../components/QuestCard'
import { StreakPanel } from '../components/StreakPanel'

export default function QuestHubPage() {
  const dashboard = useDashboard()
  const quests = useQuests()
  const achievements = useAchievements()

  // Fetch details for the first unreviewed trades (small, capped set).
  const unreviewedIds = dashboard.data?.journal.unreviewed_trade_ids.slice(0, 6) ?? []
  const unreviewedTrades = useQueries({
    queries: unreviewedIds.map((id) => ({
      queryKey: ['trade', id],
      queryFn: () => api.getTrade(id),
    })),
  })

  if (dashboard.isPending) return <LoadingState label="Connecting to mission control…" />
  if (dashboard.isError)
    return (
      <ErrorState
        message={`Backend unreachable — ${dashboard.error.message}. Start the local v2 backend and try again.`}
        onRetry={() => void dashboard.refetch()}
      />
    )

  const data = dashboard.data
  const pilot = data.pilot
  const emptyJournal =
    data.journal.trades_total === 0 &&
    data.journal.emotional_entries === 0 &&
    data.journal.quick_reviews === 0 &&
    data.journal.daily_reviews === 0 &&
    data.recent_activity.length === 0

  const activeQuests = (quests.data?.items ?? []).filter(
    (q) => !q.completed_at && q.status === 'active' && !q.opt_in,
  )
  const claimableQuests = (quests.data?.items ?? []).filter((q) => q.claimable)
  const unlockedAchievements = (achievements.data?.items ?? []).filter((a) => a.unlocked)

  if (emptyJournal) {
    return (
      <>
        <div className="topbar">
          <h1>Quest Hub</h1>
        </div>
        <Panel title="Welcome, pilot" accent elevated>
          <p className="muted" style={{ marginTop: 0 }}>
            Your journal is empty and ready. Trade Quest is a reflective trading
            journal: you log trades you have already taken, review them, note
            lessons, and build journaling habits — at your own pace, with no
            pressure.
          </p>
          <div className="onboarding">
            <div className="panel">
              <strong>Record a trade</strong>
              <p className="muted">Log an executed trade with Quick Capture.</p>
              <Link to="/quick-capture" className="btn btn-primary">
                Open Quick Capture
              </Link>
            </div>
            <div className="panel">
              <strong>Reflect</strong>
              <p className="muted">Write a Quick Review, a Deep Review, or an emotional check-in.</p>
              <Link to="/quick-review" className="btn">
                Start a review
              </Link>
            </div>
            <div className="panel">
              <strong>Check in</strong>
              <p className="muted">Daily and Weekly Reviews close each day and week.</p>
              <Link to="/daily-review" className="btn">
                Daily Review
              </Link>
            </div>
            <div className="panel">
              <strong>Set up</strong>
              <p className="muted">Define the symbols, setups and emotions you use.</p>
              <Link to="/settings" className="btn">
                Open Settings
              </Link>
            </div>
          </div>
          <p className="hint" style={{ marginTop: '1rem' }}>
            No XP, quests or achievements are shown before you actually earn
            them — the dashboard reflects your real journal only.
          </p>
        </Panel>
      </>
    )
  }

  return (
    <>
      <div className="topbar">
        <h1>Quest Hub</h1>
      </div>

      <Panel title="Pilot status" accent elevated>
        <div className="pilot">
          <div className="level-ring" aria-hidden>
            <span className="level-ring-value num">{pilot.level}</span>
          </div>
          <div style={{ flex: 1, minWidth: 240 }}>
            <p className="pilot-title">{pilot.title}</p>
            <p className="muted num" style={{ margin: 0 }}>
              {pilot.total_xp} XP total
            </p>
            <div style={{ marginTop: '0.6rem', maxWidth: 480 }}>
              {/*
                Progression is derived server-side only: `progress_pct` and
                `next_level_xp_needed` are sent as-is by the backend
                (next_level_xp_needed = XP STILL needed to reach the next
                level, never the level's total span).  Never recompute these
                from current_level_xp here.
              */}
              <ProgressBar
                value={pilot.progress_pct}
                max={100}
                gold
                label="Progress to next level"
              />
            </div>
            <p className="faint num" style={{ marginTop: '0.35rem' }}>
              {pilot.next_level_total_xp !== null
                ? `${pilot.next_level_xp_needed} XP to level ${pilot.level + 1}`
                : 'Mastery level reached'}
            </p>
          </div>
        </div>
      </Panel>

      {claimableQuests.length > 0 && (
        <Panel title="Rewards ready">
          <p className="muted">
            {claimableQuests.length} completed quest
            {claimableQuests.length === 1 ? '' : 's'} awaiting your claim.
          </p>
          <Link to="/quests" className="btn btn-gold">
            Go to Quest Center
          </Link>
        </Panel>
      )}

      {data.streak && <StreakPanel streak={data.streak} />}

      <div className="grid-2">
        <Panel
          title="Active quests"
          accent
          actions={
            <Link to="/quests" className="btn btn-sm">
              All quests
            </Link>
          }
        >
          {activeQuests.length === 0 ? (
            <p className="muted">No active quests right now.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {activeQuests.slice(0, 4).map((quest) => (
                <QuestCard key={quest.code} quest={quest} />
              ))}
            </div>
          )}
        </Panel>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <Panel title="Today">
            <ul className="activity-list">
              <li>
                <span>Daily Review</span>
                {data.journal.daily_review_done_today ? (
                  <span className="badge badge-success">Done</span>
                ) : (
                  <Link to="/daily-review" className="btn btn-sm">
                    Write
                  </Link>
                )}
              </li>
              <li>
                <span>Weekly Review</span>
                {data.journal.weekly_review_done_this_week ? (
                  <span className="badge badge-success">Done</span>
                ) : (
                  <Link to="/weekly-review" className="btn btn-sm">
                    Write
                  </Link>
                )}
              </li>
              <li>
                <span>Closed trades without a review</span>
                <span className="num">{data.journal.unreviewed_trade_ids.length}</span>
              </li>
            </ul>
          </Panel>

          <Panel
            title="Achievements"
            actions={
              <Link to="/achievements" className="btn btn-sm">
                Gallery
              </Link>
            }
          >
            <p className="muted num" style={{ margin: 0 }}>
              {data.achievements.unlocked_count} unlocked
            </p>
            {unlockedAchievements.slice(0, 3).map((a) => (
              <p key={a.code} className="muted" style={{ marginBottom: '0.25rem' }}>
                <span className="badge badge-gold">{a.name}</span> {a.description}
              </p>
            ))}
          </Panel>
        </div>
      </div>

      <Panel title="Reflection summary" accent>
        <div className="grid-stats">
          <StatTile label="Trades" value={data.journal.trades_total} />
          <StatTile label="Quick Reviews" value={data.journal.quick_reviews} />
          <StatTile label="Lessons" value={data.journal.lessons} />
          <StatTile label="Emotional entries" value={data.journal.emotional_entries} />
          <StatTile label="Daily Reviews" value={data.journal.daily_reviews} />
          <StatTile label="Open trades" value={data.journal.open_trades} />
        </div>
        <p className="hint" style={{ marginTop: '0.8rem' }}>
          Descriptive counts of your journaling only — nothing here measures or
          predicts trading performance.
        </p>
      </Panel>

      {data.recent_activity.length > 0 && (
        <Panel title="Recent activity">
          <ul className="activity-list">
            {data.recent_activity
              .slice()
              .reverse()
              .slice(-12)
              .reverse()
              .map((event) => (
                <li key={event.id}>
                  <span>
                    {eventLabel(event.event_type)}
                    {event.awarded_at && (
                      <span className="faint"> · {formatDateTime(event.awarded_at)}</span>
                    )}
                  </span>
                  <span className="activity-amount num">+{event.amount} XP</span>
                </li>
              ))}
          </ul>
        </Panel>
      )}

      {unreviewedIds.length > 0 && (
        <Panel title="Closed trades awaiting review">
          <ul className="activity-list">
            {unreviewedTrades.map((q) =>
              q.data ? (
                <li key={q.data.id}>
                  <span>
                    <Link to={`/trades/${q.data.id}`}>
                      {q.data.symbol_label}
                      {q.data.direction ? ` ${q.data.direction}` : ''}
                    </Link>
                    <span className="faint"> · closed {formatDateTime(q.data.closed_at)}</span>
                  </span>
                  <span className="row">
                    <Link to="/quick-review" className="btn btn-sm">
                      Quick Review
                    </Link>
                    <Link to="/deep-review" className="btn btn-sm">
                      Deep Review
                    </Link>
                  </span>
                </li>
              ) : null,
            )}
          </ul>
          {data.journal.unreviewed_trade_ids.length > unreviewedIds.length && (
            <p className="hint">
              Showing the first {unreviewedIds.length} of{' '}
              {data.journal.unreviewed_trade_ids.length} unreviewed trades.
            </p>
          )}
        </Panel>
      )}
    </>
  )
}
