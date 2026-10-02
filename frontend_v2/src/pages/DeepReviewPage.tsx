/**
 * Deep Review - structured post-trade reflection with lessons.
 * Saving a review and recording lessons are distinct actions (matching the
 * API).  The backend caps XP-earning lessons at three per review - additional
 * lessons are saved without being presented as XP opportunities.
 */
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useDeepReview, useInvalidation, useTrade } from '../api/hooks'
import type { DeepReviewInput, DeepReviewMutation, LessonMutation } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { Panel } from '../components/ui'
import { LoadingState } from '../components/states'
import { TradePicker } from '../components/TradePicker'

const GRADES = ['A', 'B', 'C', 'D', 'F'] as const

interface FormState {
  plan_review: string
  execution_review: string
  risk_review: string
  emotions_review: string
  mistakes: string
  grade: '' | (typeof GRADES)[number]
  key_takeaway: string
}

const EMPTY_FORM: FormState = {
  plan_review: '',
  execution_review: '',
  risk_review: '',
  emotions_review: '',
  mistakes: '',
  grade: '',
  key_takeaway: '',
}

export default function DeepReviewPage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const [tradeId, setTradeId] = useState<number | null>(null)

  const review = useDeepReview(tradeId ?? 0)
  const trade = useTrade(tradeId ?? 0)

  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [newLessons, setNewLessons] = useState<string[]>([])
  const [lessonText, setLessonText] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [created, setCreated] = useState<DeepReviewMutation | null>(null)

  useEffect(() => {
    if (review.data) {
      setForm({
        plan_review: review.data.plan_review ?? '',
        execution_review: review.data.execution_review ?? '',
        risk_review: review.data.risk_review ?? '',
        emotions_review: review.data.emotions_review ?? '',
        mistakes: review.data.mistakes ?? '',
        grade: review.data.grade ?? '',
        key_takeaway: review.data.key_takeaway ?? '',
      })
      setCreated(null)
    } else if (review.isSuccess) {
      setForm(EMPTY_FORM)
      setNewLessons([])
    }
  }, [review.data, review.isSuccess])

  const createMutation = useMutation({
    mutationFn: (input: DeepReviewInput) => api.createDeepReview(tradeId!, input),
    onSuccess: (result) => {
      toast.feedback(result, 'Deep Review')
      invalidate.journal()
      setCreated(result)
      setNewLessons([])
    },
    onError: (error) => setFormError(error.message),
  })

  const updateMutation = useMutation({
    mutationFn: (input: DeepReviewInput) => api.updateDeepReview(review.data!.id, input),
    onSuccess: () => {
      toast.success('Deep Review updated. Edits award no XP.')
      void invalidate.journal()
    },
    onError: (error) => setFormError(error.message),
  })

  const addLessonMutation = useMutation({
    mutationFn: (text: string) =>
      api.createLesson({
        source_type: 'deep',
        source_id: review.data!.id,
        trade_id: tradeId,
        text,
      }),
    onSuccess: (result: LessonMutation) => {
      // Only the server decides whether this lesson earned XP - the toast
      // stays silent when xp_awarded is 0 (cap reached).
      toast.feedback(result, 'Lesson')
      setLessonText('')
      void invalidate.journal()
    },
    onError: (error) => setFormError(error.message),
  })

  const deleteLessonMutation = useMutation({
    mutationFn: (lessonId: number) => api.deleteLesson(lessonId),
    onSuccess: () => {
      toast.success('Lesson removed. XP already earned is never taken back.')
      void invalidate.journal()
    },
    onError: (error) => toast.error(error.message),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!tradeId) return
    const input: DeepReviewInput = {
      plan_review: form.plan_review || null,
      execution_review: form.execution_review || null,
      risk_review: form.risk_review || null,
      emotions_review: form.emotions_review || null,
      mistakes: form.mistakes || null,
      grade: form.grade === '' ? null : form.grade,
      key_takeaway: form.key_takeaway || null,
    }
    if (review.data) updateMutation.mutate(input)
    else {
      input.lessons = newLessons.filter((t) => t.trim() !== '').map((t) => ({ text: t.trim() }))
      createMutation.mutate(input)
    }
  }

  const busy = createMutation.isPending || updateMutation.isPending

  return (
    <>
      <div className="topbar">
        <h1>Deep Review</h1>
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
              {trade.data.setup_label ? ` · ${trade.data.setup_label}` : ''} ·{' '}
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
          title={review.data ? 'Edit Deep Review (no XP for edits)' : 'New Deep Review'}
          accent
        >
          {review.data && (
            <p className="faint">One Deep Review per trade. Edits never re-award XP.</p>
          )}
          <form onSubmit={handleSubmit} noValidate>
            <div className="form-grid">
              <div className="full">
                <label htmlFor="dr-plan">What happened — the plan</label>
                <textarea
                  id="dr-plan"
                  value={form.plan_review}
                  onChange={(e) => setForm({ ...form, plan_review: e.target.value })}
                  placeholder="How did the setup match (or not match) your plan?"
                />
              </div>
              <div className="full">
                <label htmlFor="dr-exec">Execution review</label>
                <textarea
                  id="dr-exec"
                  value={form.execution_review}
                  onChange={(e) => setForm({ ...form, execution_review: e.target.value })}
                  placeholder="How did you execute?"
                />
              </div>
              <div className="full">
                <label htmlFor="dr-risk">Risk review</label>
                <textarea
                  id="dr-risk"
                  value={form.risk_review}
                  onChange={(e) => setForm({ ...form, risk_review: e.target.value })}
                  placeholder="How did risk management feel and work?"
                />
              </div>
              <div className="full">
                <label htmlFor="dr-emotions">Emotional context</label>
                <textarea
                  id="dr-emotions"
                  value={form.emotions_review}
                  onChange={(e) => setForm({ ...form, emotions_review: e.target.value })}
                  placeholder="What did you notice emotionally? (no judgment)"
                />
              </div>
              <div className="full">
                <label htmlFor="dr-mistakes">Mistakes</label>
                <textarea
                  id="dr-mistakes"
                  value={form.mistakes}
                  onChange={(e) => setForm({ ...form, mistakes: e.target.value })}
                  placeholder="What would you do differently?"
                />
              </div>
              <div>
                <label htmlFor="dr-grade">Overall grade (optional)</label>
                <select
                  id="dr-grade"
                  value={form.grade}
                  onChange={(e) => setForm({ ...form, grade: e.target.value as FormState['grade'] })}
                >
                  <option value="">Not graded</option>
                  {GRADES.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>
              <div className="full">
                <label htmlFor="dr-takeaway">Key takeaway</label>
                <textarea
                  id="dr-takeaway"
                  value={form.key_takeaway}
                  onChange={(e) => setForm({ ...form, key_takeaway: e.target.value })}
                  placeholder="One sentence you want to remember"
                />
              </div>
            </div>

            {!review.data && (
              <div style={{ marginTop: '1rem' }}>
                <label htmlFor="dr-lessons">Lessons recorded with this review</label>
                <p className="hint">
                  The first three lessons per review can earn XP (confirmed by the
                  server when saved). You can always record more — they are kept,
                  they simply are not XP opportunities.
                </p>
                {newLessons.map((text, i) => (
                  <div key={i} className="row" style={{ marginBottom: '0.4rem' }}>
                    <input
                      value={text}
                      onChange={(e) =>
                        setNewLessons(newLessons.map((t, j) => (j === i ? e.target.value : t)))
                      }
                      placeholder={`Lesson ${i + 1}`}
                      aria-label={`Lesson ${i + 1}`}
                    />
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => setNewLessons(newLessons.filter((_, j) => j !== i))}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => setNewLessons([...newLessons, ''])}
                >
                  Add lesson
                </button>
              </div>
            )}
            {formError && (
              <p className="error-text" role="alert">
                {formError}
              </p>
            )}
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? 'Saving…' : review.data ? 'Save changes' : 'Save Deep Review'}
              </button>
            </div>
          </form>
          {created && created.xp_awarded > 0 && (
            <p className="success-text" role="status">
              Deep Review saved — the server awarded {created.xp_awarded} XP.
            </p>
          )}
        </Panel>
      )}

      {review.data && (
        <Panel title="Lessons for this review" accent>
          {review.data.lessons.length === 0 ? (
            <p className="muted">No lessons recorded yet for this review.</p>
          ) : (
            <ul className="activity-list">
              {review.data.lessons.map((lesson) => (
                <li key={lesson.id}>
                  <span>{lesson.text}</span>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    onClick={() => deleteLessonMutation.mutate(lesson.id)}
                    disabled={deleteLessonMutation.isPending}
                    aria-label={`Remove lesson: ${lesson.text.slice(0, 40)}`}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="row" style={{ marginTop: '0.9rem' }}>
            <input
              style={{ flex: 1, minWidth: 220 }}
              value={lessonText}
              onChange={(e) => setLessonText(e.target.value)}
              placeholder="A lesson you want to remember from this trade"
              aria-label="New lesson"
            />
            <button
              type="button"
              className="btn"
              onClick={() => {
                if (lessonText.trim()) addLessonMutation.mutate(lessonText.trim())
              }}
              disabled={addLessonMutation.isPending || !lessonText.trim()}
            >
              {addLessonMutation.isPending ? 'Saving…' : 'Record lesson'}
            </button>
          </div>
          {review.data.lessons.length >= 3 && (
            <p className="hint">
              Three lessons are already recorded for this review. More can be
              saved, but they will not earn XP — the server decides and confirms.
            </p>
          )}
        </Panel>
      )}
    </>
  )
}
