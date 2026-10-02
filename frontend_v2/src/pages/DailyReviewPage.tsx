/**
 * Daily Review - one review per local calendar date (backend enforces).
 * Creation reports real XP; edits report nothing extra.
 */
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { useDailyReview, useDailyReviews, useInvalidation } from '../api/hooks'
import type { DailyReviewMutation } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { formatDate, todayIso } from '../utils/format'
import { Panel, RatingPills } from '../components/ui'
import { LoadingState } from '../components/states'

export default function DailyReviewPage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const [date, setDate] = useState(todayIso())
  const review = useDailyReview(date)
  const recent = useDailyReviews()

  const [energy, setEnergy] = useState<number | null>(null)
  const [focus, setFocus] = useState<number | null>(null)
  const [mood, setMood] = useState<number | null>(null)
  const [reflection, setReflection] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [created, setCreated] = useState<DailyReviewMutation | null>(null)

  useEffect(() => {
    setCreated(null)
    setFormError(null)
    if (review.data) {
      setEnergy(review.data.energy)
      setFocus(review.data.focus)
      setMood(review.data.mood)
      setReflection(review.data.reflection ?? '')
    } else if (review.isSuccess) {
      setEnergy(null)
      setFocus(null)
      setMood(null)
      setReflection('')
    }
  }, [review.data, review.isSuccess])

  const createMutation = useMutation({
    mutationFn: () =>
      api.createDailyReview(date, {
        energy,
        focus,
        mood,
        reflection: reflection || null,
      }),
    onSuccess: (result) => {
      toast.feedback(result, 'Daily Review')
      invalidate.journal()
      setCreated(result)
    },
    onError: (error) => setFormError(error.message),
  })

  const updateMutation = useMutation({
    mutationFn: () =>
      api.updateDailyReview(date, {
        energy,
        focus,
        mood,
        reflection: reflection || null,
      }),
    onSuccess: () => {
      toast.success('Daily Review updated. Edits award no XP.')
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
        <h1>Daily Review</h1>
      </div>

      <Panel title="Pick a date" accent>
        <label htmlFor="dr-date">Date</label>
        <input
          id="dr-date"
          type="date"
          value={date}
          max={todayIso()}
          onChange={(e) => setDate(e.target.value)}
          style={{ maxWidth: 220 }}
        />
        <p className="hint">One review per date — the server keeps it unique.</p>
      </Panel>

      {review.isPending && <LoadingState label="Loading review…" />}

      {!review.isPending && (
        <Panel
          title={review.data ? 'Edit Daily Review (no XP for edits)' : 'New Daily Review'}
          accent
        >
          <form onSubmit={handleSubmit} noValidate>
            <div className="form-grid">
              <div>
                <label id="dr-energy">Energy (1–5)</label>
                <RatingPills name="Energy" value={energy} onChange={setEnergy} allowEmpty />
              </div>
              <div>
                <label id="dr-focus">Focus (1–5)</label>
                <RatingPills name="Focus" value={focus} onChange={setFocus} allowEmpty />
              </div>
              <div>
                <label id="dr-mood">Mood (1–5)</label>
                <RatingPills name="Mood" value={mood} onChange={setMood} allowEmpty />
              </div>
              <div className="full">
                <label htmlFor="dr-reflection">Reflection</label>
                <textarea
                  id="dr-reflection"
                  value={reflection}
                  onChange={(e) => setReflection(e.target.value)}
                  placeholder="How did today go? (optional)"
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
                {busy ? 'Saving…' : review.data ? 'Save changes' : 'Save Daily Review'}
              </button>
            </div>
          </form>
          {created && created.xp_awarded > 0 && (
            <p className="success-text" role="status">
              Daily Review saved — the server awarded {created.xp_awarded} XP.
            </p>
          )}
        </Panel>
      )}

      <Panel title="Recent daily reviews">
        {recent.isPending ? (
          <LoadingState />
        ) : recent.data && recent.data.rows.length > 0 ? (
          <ul className="activity-list">
            {recent.data.rows.map((row) => (
              <li key={row.id}>
                <button type="button" className="btn btn-sm" onClick={() => setDate(row.review_date)}>
                  {formatDate(row.review_date)}
                </button>
                <span className="faint">
                  {row.energy !== null && <>energy {row.energy} · </>}
                  {row.focus !== null && <>focus {row.focus} · </>}
                  {row.mood !== null && <>mood {row.mood}</>}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No daily reviews yet.</p>
        )}
      </Panel>
    </>
  )
}
