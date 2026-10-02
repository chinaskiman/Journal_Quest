/**
 * Quick Review - concise post-trade reflection linked to one persisted trade.
 * One review per trade (backend enforces).  Creation reports the real XP from
 * the response; editing reports nothing extra (backend awards zero on edit).
 */
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useInvalidation, useQuickReview, useTrade } from '../api/hooks'
import type { QuickReviewInput, QuickReviewMutation } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { Panel, RatingPills } from '../components/ui'
import { LoadingState } from '../components/states'
import { TradePicker } from '../components/TradePicker'

export default function QuickReviewPage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const [tradeId, setTradeId] = useState<number | null>(null)

  const review = useQuickReview(tradeId ?? 0)
  const trade = useTrade(tradeId ?? 0)

  const [followedPlan, setFollowedPlan] = useState<'yes' | 'partly' | 'no' | null>(null)
  const [executionRating, setExecutionRating] = useState<number | null>(null)
  const [wentWell, setWentWell] = useState('')
  const [wentWrong, setWentWrong] = useState('')
  const [improve, setImprove] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [created, setCreated] = useState<QuickReviewMutation | null>(null)

  // Populate the form when the saved review loads (or a new trade is picked).
  useEffect(() => {
    if (review.data) {
      setFollowedPlan(review.data.followed_plan)
      setExecutionRating(review.data.execution_rating)
      setWentWell(review.data.went_well ?? '')
      setWentWrong(review.data.went_wrong ?? '')
      setImprove(review.data.improve ?? '')
      setCreated(null)
    } else if (review.isSuccess) {
      setFollowedPlan(null)
      setExecutionRating(null)
      setWentWell('')
      setWentWrong('')
      setImprove('')
    }
  }, [review.data, review.isSuccess])

  const payload = (): QuickReviewInput | null => {
    if (executionRating === null) {
      setFormError('Execution rating (1–5) is required.')
      return null
    }
    setFormError(null)
    return {
      followed_plan: followedPlan,
      execution_rating: executionRating,
      went_well: wentWell || null,
      went_wrong: wentWrong || null,
      improve: improve || null,
    }
  }

  const createMutation = useMutation({
    mutationFn: (input: QuickReviewInput) => api.createQuickReview(tradeId!, input),
    onSuccess: (result) => {
      toast.feedback(result, 'Quick Review')
      invalidate.journal()
      setCreated(result)
    },
    onError: (error) => setFormError(error.message),
  })

  const updateMutation = useMutation({
    mutationFn: (input: QuickReviewInput) => api.updateQuickReview(review.data!.id, input),
    onSuccess: () => {
      toast.success('Quick Review updated. Edits award no XP.')
      void invalidate.journal()
    },
    onError: (error) => setFormError(error.message),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const input = payload()
    if (!input || !tradeId) return
    if (review.data) updateMutation.mutate(input)
    else createMutation.mutate(input)
  }

  const busy = createMutation.isPending || updateMutation.isPending

  return (
    <>
      <div className="topbar">
        <h1>Quick Review</h1>
      </div>

      <Panel title="Choose a trade" accent>
        <TradePicker selectedId={tradeId} onSelect={setTradeId} label="Trade to review" />
      </Panel>

      {tradeId !== null && (
        <Panel title="Trade context">
          {trade.isPending ? (
            <LoadingState />
          ) : trade.data ? (
            <p className="muted" style={{ margin: 0 }}>
              #{trade.data.id} · {trade.data.symbol_label}
              {trade.data.setup_label ? ` · ${trade.data.setup_label}` : ''}
              {trade.data.direction ? ` · ${trade.data.direction}` : ''} ·{' '}
              <Link to={`/trades/${trade.data.id}`}>view trade</Link>
            </p>
          ) : (
            <p className="muted">Trade unavailable.</p>
          )}
        </Panel>
      )}

      {tradeId !== null && review.isPending && <LoadingState label="Loading review…" />}

      {tradeId !== null && !review.isPending && (
        <Panel
          title={review.data ? 'Edit Quick Review (no XP for edits)' : 'New Quick Review'}
          accent
        >
          {review.data && (
            <p className="faint">
              A Quick Review already exists for this trade — one per trade. Saving
              changes updates it and awards no additional XP.
            </p>
          )}
          <form onSubmit={handleSubmit} noValidate>
            <div className="form-grid">
              <div className="full">
                <label id="qr-plan-label">Did you follow your plan?</label>
                <div className="radio-pills" role="group" aria-labelledby="qr-plan-label">
                  {(['yes', 'partly', 'no'] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      className="pill"
                      aria-pressed={followedPlan === option}
                      onClick={() => setFollowedPlan(followedPlan === option ? null : option)}
                    >
                      {option === 'yes' ? 'Yes' : option === 'partly' ? 'Partly' : 'No'}
                    </button>
                  ))}
                  <button
                    type="button"
                    className="pill"
                    aria-pressed={followedPlan === null}
                    onClick={() => setFollowedPlan(null)}
                  >
                    —
                  </button>
                </div>
              </div>
              <div className="full">
                <label id="qr-rating-label">
                  Execution rating (1–5) <span className="req" aria-hidden>*</span>
                </label>
                <RatingPills
                  name="Execution rating"
                  value={executionRating}
                  onChange={setExecutionRating}
                />
              </div>
              <div className="full">
                <label htmlFor="qr-well">What went well?</label>
                <textarea
                  id="qr-well"
                  value={wentWell}
                  onChange={(e) => setWentWell(e.target.value)}
                  placeholder="Keep it short and specific (optional)"
                />
              </div>
              <div className="full">
                <label htmlFor="qr-wrong">What went wrong?</label>
                <textarea
                  id="qr-wrong"
                  value={wentWrong}
                  onChange={(e) => setWentWrong(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="full">
                <label htmlFor="qr-improve">What will you improve?</label>
                <textarea
                  id="qr-improve"
                  value={improve}
                  onChange={(e) => setImprove(e.target.value)}
                  placeholder="Optional"
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
                {busy ? 'Saving…' : review.data ? 'Save changes' : 'Save Quick Review'}
              </button>
            </div>
          </form>
          {created && (
            <p className="success-text" role="status">
              Quick Review saved
              {created.xp_awarded > 0 ? ` — the server awarded ${created.xp_awarded} XP.` : '.'}
            </p>
          )}
        </Panel>
      )}
    </>
  )
}
