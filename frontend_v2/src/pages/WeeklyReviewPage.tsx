/**
 * Weekly Review - one review per ISO week (backend enforces, key "YYYY-Www").
 * Includes the optional `advice_to_future_me` field; null (older records or
 * simply not written) is displayed as "no advice recorded", never invented.
 */
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { useInvalidation, useWeeklyReview, useWeeklyReviews } from '../api/hooks'
import type { WeeklyReviewMutation } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { currentIsoWeek, isoWeekLabel } from '../utils/format'
import { Panel } from '../components/ui'
import { LoadingState } from '../components/states'

export default function WeeklyReviewPage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const [week, setWeek] = useState(currentIsoWeek())
  const review = useWeeklyReview(week)
  const recent = useWeeklyReviews()

  const [highlights, setHighlights] = useState('')
  const [challenges, setChallenges] = useState('')
  const [patterns, setPatterns] = useState('')
  const [planNextWeek, setPlanNextWeek] = useState('')
  const [advice, setAdvice] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [created, setCreated] = useState<WeeklyReviewMutation | null>(null)

  useEffect(() => {
    setCreated(null)
    setFormError(null)
    if (review.data) {
      setHighlights(review.data.highlights ?? '')
      setChallenges(review.data.challenges ?? '')
      setPatterns(review.data.patterns ?? '')
      setPlanNextWeek(review.data.plan_next_week ?? '')
      setAdvice(review.data.advice_to_future_me ?? '')
    } else if (review.isSuccess) {
      setHighlights('')
      setChallenges('')
      setPatterns('')
      setPlanNextWeek('')
      setAdvice('')
    }
  }, [review.data, review.isSuccess])

  const payload = () => ({
    highlights: highlights || null,
    challenges: challenges || null,
    patterns: patterns || null,
    plan_next_week: planNextWeek || null,
    advice_to_future_me: advice || null,
  })

  const createMutation = useMutation({
    mutationFn: () => api.createWeeklyReview(week, payload()),
    onSuccess: (result) => {
      toast.feedback(result, 'Weekly Review')
      invalidate.journal()
      setCreated(result)
    },
    onError: (error) => setFormError(error.message),
  })

  const updateMutation = useMutation({
    mutationFn: () => api.updateWeeklyReview(week, payload()),
    onSuccess: () => {
      toast.success('Weekly Review updated. Edits award no XP.')
      void invalidate.journal()
    },
    onError: (error) => setFormError(error.message),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (review.data) updateMutation.mutate()
    else createMutation.mutate()
  }

  const busy = createMutation.isPending || updateMutation.isPending

  return (
    <>
      <div className="topbar">
        <h1>Weekly Review</h1>
      </div>

      <Panel title="Pick an ISO week" accent>
        <label htmlFor="wr-week">Week</label>
        <input
          id="wr-week"
          type="week"
          value={week}
          onChange={(e) => setWeek(e.target.value)}
          style={{ maxWidth: 220 }}
        />
        <p className="hint">{isoWeekLabel(week)} — one review per week, enforced by the server.</p>
      </Panel>

      {review.isPending && <LoadingState label="Loading review…" />}

      {!review.isPending && (
        <Panel
          title={review.data ? 'Edit Weekly Review (no XP for edits)' : 'New Weekly Review'}
          accent
        >
          {review.data && review.data.advice_to_future_me === null && (
            <p className="faint">
              No advice to future you was recorded for this week — the field
              below is available whenever you want to add it.
            </p>
          )}
          <form onSubmit={handleSubmit} noValidate>
            <div className="form-grid">
              <div className="full">
                <label htmlFor="wr-highlights">Highlights</label>
                <textarea
                  id="wr-highlights"
                  value={highlights}
                  onChange={(e) => setHighlights(e.target.value)}
                  placeholder="What went well this week? (optional)"
                />
              </div>
              <div className="full">
                <label htmlFor="wr-challenges">Challenges</label>
                <textarea
                  id="wr-challenges"
                  value={challenges}
                  onChange={(e) => setChallenges(e.target.value)}
                  placeholder="What was difficult? (optional)"
                />
              </div>
              <div className="full">
                <label htmlFor="wr-patterns">Patterns</label>
                <textarea
                  id="wr-patterns"
                  value={patterns}
                  onChange={(e) => setPatterns(e.target.value)}
                  placeholder="Recurring themes you noticed (optional)"
                />
              </div>
              <div className="full">
                <label htmlFor="wr-plan">Plan for next week</label>
                <textarea
                  id="wr-plan"
                  value={planNextWeek}
                  onChange={(e) => setPlanNextWeek(e.target.value)}
                  placeholder="Journaling focus for next week (optional)"
                />
              </div>
              <div className="full">
                <label htmlFor="wr-advice">Advice to future me (optional)</label>
                <textarea
                  id="wr-advice"
                  value={advice}
                  onChange={(e) => setAdvice(e.target.value)}
                  placeholder="A note for the future version of you"
                />
              </div>
            </div>
            {formError && (
              <p className="error-text" role="alert">
                {formError}
              </p>
            )}
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? 'Saving…' : review.data ? 'Save changes' : 'Save Weekly Review'}
              </button>
            </div>
          </form>
          {created && created.xp_awarded > 0 && (
            <p className="success-text" role="status">
              Weekly Review saved — the server awarded {created.xp_awarded} XP.
            </p>
          )}
        </Panel>
      )}

      <Panel title="Previous weekly reviews">
        {recent.isPending ? (
          <LoadingState />
        ) : recent.data && recent.data.rows.length > 0 ? (
          <ul className="activity-list">
            {recent.data.rows.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() =>
                    setWeek(`${row.iso_year}-W${String(row.iso_week).padStart(2, '0')}`)
                  }
                >
                  {isoWeekLabel(`${row.iso_year}-W${String(row.iso_week).padStart(2, '0')}`)}
                </button>
                <span className="faint">
                  {row.advice_to_future_me ? 'includes advice to future you' : 'no advice recorded'}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No weekly reviews yet.</p>
        )}
      </Panel>
    </>
  )
}
