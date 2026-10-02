/**
 * Trade details - the full persisted record, associated reflections, and
 * screenshot.  Editing/closing/deleting award no XP by design; the UI never
 * shows an XP celebration for these operations.
 */
import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { qk } from '../api/keys'
import { useDeepReview, useEmotionalEntries, useQuickReview, useSettings, useTrade } from '../api/hooks'
import type { Trade, TradeResult, TradeUpdateInput } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { formatDateTime, formatNumber } from '../utils/format'
import { ConfirmDialog, Panel } from '../components/ui'
import { EmptyState, ErrorState, LoadingState } from '../components/states'

function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function Screenshot({ tradeId }: { tradeId: number }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [tradeId])
  if (failed) {
    return (
      <p className="muted">
        Screenshot unavailable. It may be outside the server's permitted
        directories, missing on disk, or too large — see Settings for guidance.
      </p>
    )
  }
  return (
    <div className="screenshot-frame">
      <img
        src={api.screenshotUrl(tradeId)}
        alt={`Screenshot for trade #${tradeId}`}
        onError={() => setFailed(true)}
        loading="lazy"
      />
    </div>
  )
}

export default function TradeDetailPage() {
  const { id } = useParams()
  const tradeId = Number(id)
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const invalidate = { journal: () => void queryClient.invalidateQueries() }

  const tradeQuery = useTrade(tradeId)
  const quickReview = useQuickReview(tradeId)
  const deepReview = useDeepReview(tradeId)
  const emotional = useEmotionalEntries({ trade_id: tradeId })
  const symbols = useSettings('symbols')
  const setups = useSettings('setups')

  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<Record<string, string>>({})
  const [closeForm, setCloseForm] = useState({ closed_at: '', exit_price: '', user_pnl: '', result: '', result_note: '' })
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const trade: Trade | undefined = tradeQuery.data

  useEffect(() => {
    if (trade && !editing) {
      setForm({
        symbol: trade.symbol_label,
        setup: trade.setup_label ?? '',
        direction: trade.direction ?? '',
        opened_at: toLocalInput(trade.opened_at),
        entry_price: trade.entry_price?.toString() ?? '',
        exit_price: trade.exit_price?.toString() ?? '',
        user_pnl: trade.user_pnl?.toString() ?? '',
        result: trade.result ?? '',
        result_note: trade.result_note ?? '',
        thesis: trade.thesis ?? '',
        notes: trade.notes ?? '',
        screenshot_path: trade.screenshot_path ?? '',
      })
    }
  }, [trade, editing])

  const saveMutation = useMutation({
    mutationFn: (payload: TradeUpdateInput) => api.updateTrade(tradeId, payload),
    onSuccess: () => {
      toast.success('Trade updated. No XP is awarded for edits.')
      setEditing(false)
      void queryClient.invalidateQueries({ queryKey: ['trade', tradeId] })
      void queryClient.invalidateQueries({ queryKey: ['trades'] })
    },
    onError: (error) => setFormError(error.message),
  })

  const closeMutation = useMutation({
    mutationFn: () =>
      api.closeTrade(tradeId, {
        closed_at: closeForm.closed_at || null,
        exit_price: closeForm.exit_price === '' ? null : Number(closeForm.exit_price),
        user_pnl: closeForm.user_pnl === '' ? null : Number(closeForm.user_pnl),
        result: (closeForm.result as TradeResult) || null,
        result_note: closeForm.result_note || null,
      }),
    onSuccess: () => {
      toast.success('Trade closed. Closing awards no XP.')
      invalidate.journal()
      void queryClient.invalidateQueries({ queryKey: ['trade', tradeId] })
    },
    onError: (error) => setFormError(error.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteTrade(tradeId),
    onSuccess: () => {
      toast.success('Trade removed from the journal.')
      invalidate.journal()
      navigate('/trades')
    },
    onError: (error) => toast.error(error.message),
  })

  if (Number.isNaN(tradeId)) {
    return <ErrorState message="Invalid trade id." />
  }
  if (tradeQuery.isPending) return <LoadingState />
  if (tradeQuery.isError) return <ErrorState message={tradeQuery.error.message} onRetry={() => void tradeQuery.refetch()} />
  if (!trade) return <EmptyState title="Trade not found" />

  function submitEdit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    saveMutation.mutate({
      symbol: form.symbol,
      setup: form.setup || null,
      direction: (form.direction as 'long' | 'short' | '') || null,
      opened_at: form.opened_at,
      entry_price: form.entry_price === '' ? null : Number(form.entry_price),
      exit_price: form.exit_price === '' ? null : Number(form.exit_price),
      user_pnl: form.user_pnl === '' ? null : Number(form.user_pnl),
      result: (form.result as TradeResult) || null,
      result_note: form.result_note || null,
      thesis: form.thesis || null,
      notes: form.notes || null,
      screenshot_path: form.screenshot_path || null,
    })
  }

  return (
    <>
      <div className="topbar">
        <h1>
          {trade.symbol_label}
          <span className="faint"> · trade #{trade.id}</span>
        </h1>
        <div className="topbar-actions">
          {!editing && (
            <button type="button" className="btn" onClick={() => setEditing(true)}>
              Edit
            </button>
          )}
          {trade.status === 'open' && <span className="badge badge-cyan">Open</span>}
          {trade.status === 'closed' && <span className="badge badge-muted">Closed</span>}
        </div>
      </div>

      <div className="detail-grid">
        <Panel title="Record" accent>
          <dl className="kv-list">
            <dt>Symbol</dt>
            <dd>{trade.symbol_label}</dd>
            <dt>Setup</dt>
            <dd>{trade.setup_label ?? '—'}</dd>
            <dt>Direction</dt>
            <dd>{trade.direction ?? '—'}</dd>
            <dt>Opened</dt>
            <dd>{formatDateTime(trade.opened_at)}</dd>
            <dt>Closed</dt>
            <dd>{trade.closed_at ? formatDateTime(trade.closed_at) : '—'}</dd>
            <dt>Entry price</dt>
            <dd>{trade.entry_price === null ? '—' : formatNumber(trade.entry_price)}</dd>
            <dt>Exit price</dt>
            <dd>{trade.exit_price === null ? '—' : formatNumber(trade.exit_price)}</dd>
            <dt>Result (manual)</dt>
            <dd>{trade.result ?? '—'}</dd>
            <dt>P&L (manual)</dt>
            <dd>{trade.user_pnl === null ? '—' : formatNumber(trade.user_pnl)}</dd>
            <dt>Result note</dt>
            <dd>{trade.result_note ?? '—'}</dd>
          </dl>
          {trade.thesis && (
            <>
              <hr className="divider" />
              <h3>Thesis</h3>
              <p className="muted">{trade.thesis}</p>
            </>
          )}
          {trade.notes && (
            <>
              <h3>Notes</h3>
              <p className="muted">{trade.notes}</p>
            </>
          )}
        </Panel>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <Panel title="Screenshot">
            {trade.screenshot_path ? (
              <Screenshot tradeId={trade.id} />
            ) : (
              <p className="muted">No screenshot reference stored for this trade.</p>
            )}
          </Panel>

          <Panel title="Reflections">
            <p className="muted" style={{ margin: 0 }}>
              Quick Review:{' '}
              {quickReview.isPending ? '…' : quickReview.data ? (
                <span className="success-text">completed</span>
              ) : (
                'not written'
              )}{' '}
              · <Link to="/quick-review">open</Link>
            </p>
            <p className="muted">
              Deep Review:{' '}
              {deepReview.isPending ? '…' : deepReview.data ? (
                <span className="success-text">completed</span>
              ) : (
                'not written'
              )}{' '}
              · <Link to="/deep-review">open</Link>
            </p>
            <p className="muted">
              Emotional entries: {emotional.isPending ? '…' : (emotional.data?.total ?? 0)}
            </p>
            {emotional.data && emotional.data.rows.length > 0 && (
              <ul className="activity-list">
                {emotional.data.rows.slice(0, 3).map((entry) => (
                  <li key={entry.id}>
                    <span>
                      {entry.emotion_label} · intensity {entry.intensity}
                    </span>
                    <span className="faint">{entry.local_date}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      {editing && (
        <Panel title="Edit trade (no XP)" accent>
          <form onSubmit={submitEdit} noValidate>
            <div className="form-grid">
              <div>
                <label htmlFor="te-symbol">Symbol</label>
                <select
                  id="te-symbol"
                  value={form.symbol}
                  onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                >
                  {symbols.data?.items.map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                  {!symbols.data?.items.some((s) => s.name === trade.symbol_label) && (
                    <option value={trade.symbol_label}>{trade.symbol_label} (historical)</option>
                  )}
                </select>
              </div>
              <div>
                <label htmlFor="te-setup">Setup</label>
                <select
                  id="te-setup"
                  value={form.setup}
                  onChange={(e) => setForm({ ...form, setup: e.target.value })}
                >
                  <option value="">None</option>
                  {setups.data?.items.map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                  {trade.setup_label && !setups.data?.items.some((s) => s.name === trade.setup_label) && (
                    <option value={trade.setup_label}>{trade.setup_label} (historical)</option>
                  )}
                </select>
              </div>
              <div>
                <label htmlFor="te-direction">Direction</label>
                <select
                  id="te-direction"
                  value={form.direction}
                  onChange={(e) => setForm({ ...form, direction: e.target.value })}
                >
                  <option value="">—</option>
                  <option value="long">Long</option>
                  <option value="short">Short</option>
                </select>
              </div>
              <div>
                <label htmlFor="te-opened">Opened at</label>
                <input
                  id="te-opened"
                  type="datetime-local"
                  value={form.opened_at}
                  onChange={(e) => setForm({ ...form, opened_at: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="te-entry">Entry price</label>
                <input
                  id="te-entry"
                  type="number"
                  step="any"
                  value={form.entry_price}
                  onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="te-exit">Exit price</label>
                <input
                  id="te-exit"
                  type="number"
                  step="any"
                  value={form.exit_price}
                  onChange={(e) => setForm({ ...form, exit_price: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="te-result">Result (manual)</label>
                <select
                  id="te-result"
                  value={form.result}
                  onChange={(e) => setForm({ ...form, result: e.target.value })}
                >
                  <option value="">Not set</option>
                  <option value="win">Win</option>
                  <option value="loss">Loss</option>
                  <option value="breakeven">Breakeven</option>
                </select>
              </div>
              <div>
                <label htmlFor="te-pnl">P&L (manual)</label>
                <input
                  id="te-pnl"
                  type="number"
                  step="any"
                  value={form.user_pnl}
                  onChange={(e) => setForm({ ...form, user_pnl: e.target.value })}
                />
              </div>
              <div className="full">
                <label htmlFor="te-screenshot">Screenshot path</label>
                <input
                  id="te-screenshot"
                  value={form.screenshot_path}
                  onChange={(e) => setForm({ ...form, screenshot_path: e.target.value })}
                />
              </div>
              <div className="full">
                <label htmlFor="te-result-note">Result note</label>
                <input
                  id="te-result-note"
                  value={form.result_note}
                  onChange={(e) => setForm({ ...form, result_note: e.target.value })}
                />
              </div>
              <div className="full">
                <label htmlFor="te-thesis">Thesis</label>
                <textarea
                  id="te-thesis"
                  value={form.thesis}
                  onChange={(e) => setForm({ ...form, thesis: e.target.value })}
                />
              </div>
              <div className="full">
                <label htmlFor="te-notes">Notes</label>
                <textarea
                  id="te-notes"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </div>
            </div>
            {formError && (
              <p className="error-text" role="alert">
                {formError}
              </p>
            )}
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? 'Saving…' : 'Save changes'}
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => setEditing(false)}
                disabled={saveMutation.isPending}
              >
                Cancel
              </button>
            </div>
          </form>
        </Panel>
      )}

      {trade.status === 'open' && (
        <Panel title="Close trade (no XP)">
          <p className="muted">Closing records your manual outcome. Nothing about the close earns XP.</p>
          <div className="form-grid">
            <div>
              <label htmlFor="tc-closed">Closed at</label>
              <input
                id="tc-closed"
                type="datetime-local"
                value={closeForm.closed_at}
                onChange={(e) => setCloseForm({ ...closeForm, closed_at: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="tc-exit">Exit price</label>
              <input
                id="tc-exit"
                type="number"
                step="any"
                value={closeForm.exit_price}
                onChange={(e) => setCloseForm({ ...closeForm, exit_price: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="tc-pnl">P&L (manual)</label>
              <input
                id="tc-pnl"
                type="number"
                step="any"
                value={closeForm.user_pnl}
                onChange={(e) => setCloseForm({ ...closeForm, user_pnl: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="tc-result">Result (manual)</label>
              <select
                id="tc-result"
                value={closeForm.result}
                onChange={(e) => setCloseForm({ ...closeForm, result: e.target.value })}
              >
                <option value="">Not set</option>
                <option value="win">Win</option>
                <option value="loss">Loss</option>
                <option value="breakeven">Breakeven</option>
              </select>
            </div>
            <div className="full">
              <label htmlFor="tc-note">Result note</label>
              <input
                id="tc-note"
                value={closeForm.result_note}
                onChange={(e) => setCloseForm({ ...closeForm, result_note: e.target.value })}
              />
            </div>
          </div>
          <div className="form-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => closeMutation.mutate()}
              disabled={closeMutation.isPending}
            >
              {closeMutation.isPending ? 'Closing…' : 'Close trade'}
            </button>
          </div>
        </Panel>
      )}

      <Panel title="Danger zone">
        <p className="muted">
          Removing a trade keeps the XP ledger untouched (no clawback). The trade
          disappears from your journal lists.
        </p>
        <button type="button" className="btn btn-danger" onClick={() => setConfirmDelete(true)}>
          Remove trade
        </button>
      </Panel>

      <ConfirmDialog
        open={confirmDelete}
        title="Remove this trade?"
        message={`Trade #${trade.id} (${trade.symbol_label}) will be removed from your journal. Recorded XP is never taken back.`}
        confirmLabel="Remove trade"
        danger
        busy={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  )
}
