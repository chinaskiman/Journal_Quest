/**
 * Emotional Journal - neutral, non-judgmental emotional records.
 * No emotion is labeled good/bad/strong/weak; no diagnoses; no streak or
 * missed-day pressure.  XP display comes only from the server response.
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useEmotionalEntries, useInvalidation, useSettings } from '../api/hooks'
import type { EmotionalEntryMutation } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { formatDateTime } from '../utils/format'
import { ConfirmDialog, Panel, RatingPills } from '../components/ui'
import { EmptyState, ErrorState, LoadingState } from '../components/states'

export default function EmotionalPage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const emotions = useSettings('emotions')
  const [page, setPage] = useState(1)
  const entries = useEmotionalEntries({ page })

  const [emotion, setEmotion] = useState('')
  const [intensity, setIntensity] = useState<number | null>(null)
  const [occurredAt, setOccurredAt] = useState('')
  const [tradeId, setTradeId] = useState('')
  const [trigger, setTrigger] = useState('')
  const [body, setBody] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [created, setCreated] = useState<EmotionalEntryMutation | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const createMutation = useMutation({
    mutationFn: () =>
      api.createEmotionalEntry({
        emotion,
        intensity: intensity ?? 3,
        occurred_at: occurredAt || null,
        trade_id: tradeId === '' ? null : Number(tradeId),
        trigger: trigger || null,
        body: body || null,
      }),
    onSuccess: (result) => {
      toast.feedback(result, 'Emotional Journal')
      invalidate.journal()
      setCreated(result)
      setTrigger('')
      setBody('')
    },
    onError: (error) => setFormError(error.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteEmotionalEntry(id),
    onSuccess: () => {
      toast.success('Entry removed. XP already earned is never taken back.')
      void invalidate.journal()
      setDeletingId(null)
    },
    onError: (error) => toast.error(error.message),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!emotion) {
      setFormError('Emotion is required.')
      return
    }
    if (intensity === null) {
      setFormError('Intensity (1–5) is required.')
      return
    }
    setFormError(null)
    createMutation.mutate()
  }

  return (
    <>
      <div className="topbar">
        <h1>Emotional Journal</h1>
      </div>

      <Panel title="Record how you felt" accent>
        <p className="muted" style={{ marginTop: 0 }}>
          A check-in with yourself, not a performance review. The first entry each
          local day earns more XP than later entries that day — the server
          confirms the exact amount when you save.
        </p>
        {emotions.isPending ? (
          <LoadingState />
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            <div className="form-grid">
              <div>
                <label htmlFor="ej-emotion">
                  Emotion <span className="req" aria-hidden>*</span>
                </label>
                <select
                  id="ej-emotion"
                  value={emotion}
                  onChange={(e) => setEmotion(e.target.value)}
                  required
                >
                  <option value="">Select emotion…</option>
                  {emotions.data?.items.map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </select>
                {emotions.data?.items.length === 0 && (
                  <p className="hint">
                    No emotions defined — add them in{' '}
                    <Link to="/settings">Settings → Emotions</Link> first.
                  </p>
                )}
              </div>
              <div>
                <label id="ej-intensity-label">
                  Intensity (1–5) <span className="req" aria-hidden>*</span>
                </label>
                <RatingPills name="Intensity" value={intensity} onChange={setIntensity} />
              </div>
              <div>
                <label htmlFor="ej-occurred">When (optional)</label>
                <input
                  id="ej-occurred"
                  type="datetime-local"
                  value={occurredAt}
                  onChange={(e) => setOccurredAt(e.target.value)}
                />
                <p className="hint">Leave empty to use the current time.</p>
              </div>
              <div>
                <label htmlFor="ej-trade">Linked trade (optional)</label>
                <input
                  id="ej-trade"
                  type="number"
                  value={tradeId}
                  onChange={(e) => setTradeId(e.target.value)}
                  placeholder="Trade id"
                />
              </div>
              <div className="full">
                <label htmlFor="ej-trigger">Trigger</label>
                <input
                  id="ej-trigger"
                  value={trigger}
                  onChange={(e) => setTrigger(e.target.value)}
                  placeholder="What was happening around this feeling? (optional)"
                />
              </div>
              <div className="full">
                <label htmlFor="ej-body">Notes</label>
                <textarea
                  id="ej-body"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Describe it in your own words (optional)"
                />
              </div>
            </div>
            {formError && (
              <p className="error-text" role="alert">
                {formError}
              </p>
            )}
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Saving…' : 'Save entry'}
              </button>
            </div>
          </form>
        )}
        {created && created.xp_awarded > 0 && (
          <p className="success-text" role="status">
            Entry saved — the server awarded {created.xp_awarded} XP.
          </p>
        )}
      </Panel>

      <Panel title="Previous entries" accent>
        {entries.isPending ? (
          <LoadingState label="Loading entries…" />
        ) : entries.isError ? (
          <ErrorState message={entries.error.message} onRetry={() => void entries.refetch()} />
        ) : !entries.data || entries.data.total === 0 ? (
          <EmptyState title="No emotional entries yet" description="Your check-ins will appear here." />
        ) : (
          <>
            <ul className="activity-list">
              {entries.data.rows.map((entry) => (
                <li key={entry.id}>
                  <span>
                    <span className="badge badge-cyan">{entry.emotion_label}</span>{' '}
                    · intensity {entry.intensity}
                    {entry.trade_id !== null && (
                      <>
                        {' '}
                        · <Link to={`/trades/${entry.trade_id}`}>trade #{entry.trade_id}</Link>
                      </>
                    )}
                    {entry.trigger && <div className="faint">Trigger: {entry.trigger}</div>}
                    {entry.body && <div className="muted">{entry.body}</div>}
                  </span>
                  <span className="row">
                    <span className="faint">{formatDateTime(entry.occurred_at)}</span>
                    <button
                      type="button"
                      className="btn btn-sm btn-danger"
                      onClick={() => setDeletingId(entry.id)}
                    >
                      Remove
                    </button>
                  </span>
                </li>
              ))}
            </ul>
            <div className="row spread" style={{ marginTop: '0.9rem' }}>
              <span className="faint">{entries.data.total} entries</span>
              <div className="row">
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={entries.data.rows.length < 50}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </Panel>

      <ConfirmDialog
        open={deletingId !== null}
        title="Remove this entry?"
        message="The entry will be removed from your journal. XP already earned is never taken back."
        confirmLabel="Remove entry"
        danger
        busy={deleteMutation.isPending}
        onConfirm={() => deletingId !== null && deleteMutation.mutate(deletingId)}
        onCancel={() => setDeletingId(null)}
      />
    </>
  )
}
