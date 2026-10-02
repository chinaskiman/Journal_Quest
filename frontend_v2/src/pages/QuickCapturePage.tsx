/**
 * Quick Capture - fast recording of an ALREADY-EXECUTED trade.
 * No execution, orders, broker integration, or recommendations.  Result and
 * P&L are manually entered only (never computed).  XP/level feedback comes
 * exclusively from the backend response (xp_awarded / level_up).
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useInvalidation, useSettings } from '../api/hooks'
import type { TradeCreateInput, TradeMutation, TradeResult, TradeStatus } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { nowDateTimeLocal } from '../utils/format'
import { Panel } from '../components/ui'
import { LoadingState } from '../components/states'

export default function QuickCapturePage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const symbols = useSettings('symbols')
  const setups = useSettings('setups')

  const [symbol, setSymbol] = useState('')
  const [setup, setSetup] = useState('')
  const [direction, setDirection] = useState<'long' | 'short' | null>(null)
  const [openedAt, setOpenedAt] = useState(nowDateTimeLocal())
  const [entryPrice, setEntryPrice] = useState('')
  const [status, setStatus] = useState<TradeStatus>('open')
  const [closedAt, setClosedAt] = useState('')
  const [result, setResult] = useState<TradeResult | ''>('')
  const [exitPrice, setExitPrice] = useState('')
  const [userPnl, setUserPnl] = useState('')
  const [resultNote, setResultNote] = useState('')
  const [thesis, setThesis] = useState('')
  const [notes, setNotes] = useState('')
  const [screenshotPath, setScreenshotPath] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [created, setCreated] = useState<TradeMutation | null>(null)

  const mutation = useMutation({
    mutationFn: (payload: TradeCreateInput) => api.createTrade(payload),
    onSuccess: (trade) => {
      setFormError(null)
      toast.feedback(trade, 'Quick Capture')
      invalidate.journal()
      setCreated(trade)
    },
    onError: (error) => setFormError(error.message),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!symbol) {
      setFormError('Symbol is required.')
      return
    }
    if (!openedAt) {
      setFormError('Open date/time is required.')
      return
    }
    const payload: TradeCreateInput = {
      symbol,
      setup: setup || null,
      direction,
      opened_at: openedAt,
      entry_price: entryPrice === '' ? null : Number(entryPrice),
      status,
      closed_at: status === 'closed' ? closedAt || openedAt : null,
      result: status === 'closed' && result !== '' ? result : null,
      exit_price: status === 'closed' && exitPrice !== '' ? Number(exitPrice) : null,
      user_pnl: userPnl === '' ? null : Number(userPnl),
      result_note: resultNote || null,
      thesis: thesis || null,
      notes: notes || null,
      screenshot_path: screenshotPath || null,
    }
    mutation.mutate(payload)
  }

  if (symbols.isPending || setups.isPending) return <LoadingState />

  return (
    <>
      <div className="topbar">
        <h1>Quick Capture</h1>
      </div>
      <Panel title="Record an executed trade" accent>
        <p className="muted" style={{ marginTop: 0 }}>
          Log a trade you have already taken. Results and P&L are your own manual
          entries — the app never computes or judges them.
        </p>
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-grid">
            <div>
              <label htmlFor="qc-symbol">
                Symbol <span className="req" aria-hidden>*</span>
              </label>
              <select
                id="qc-symbol"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                required
              >
                <option value="">Select symbol…</option>
                {symbols.data?.items.map((s) => (
                  <option key={s.id} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
              {symbols.data?.items.length === 0 && (
                <p className="hint">
                  No symbols yet — create them in{' '}
                  <Link to="/settings">Settings → Symbols</Link> first.
                </p>
              )}
            </div>
            <div>
              <label htmlFor="qc-setup">Setup</label>
              <select id="qc-setup" value={setup} onChange={(e) => setSetup(e.target.value)}>
                <option value="">None</option>
                {setups.data?.items.map((s) => (
                  <option key={s.id} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label id="qc-direction-label">Direction</label>
              <div className="radio-pills" role="group" aria-labelledby="qc-direction-label">
                <button
                  type="button"
                  className="pill"
                  aria-pressed={direction === 'long'}
                  onClick={() => setDirection(direction === 'long' ? null : 'long')}
                >
                  Long
                </button>
                <button
                  type="button"
                  className="pill"
                  aria-pressed={direction === 'short'}
                  onClick={() => setDirection(direction === 'short' ? null : 'short')}
                >
                  Short
                </button>
              </div>
            </div>
            <div>
              <label htmlFor="qc-opened">
                Opened at <span className="req" aria-hidden>*</span>
              </label>
              <input
                id="qc-opened"
                type="datetime-local"
                value={openedAt}
                onChange={(e) => setOpenedAt(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="qc-entry">Entry price (optional)</label>
              <input
                id="qc-entry"
                type="number"
                step="any"
                value={entryPrice}
                onChange={(e) => setEntryPrice(e.target.value)}
              />
            </div>
            <div>
              <label id="qc-status-label">Trade status</label>
              <div className="radio-pills" role="group" aria-labelledby="qc-status-label">
                <button
                  type="button"
                  className="pill"
                  aria-pressed={status === 'open'}
                  onClick={() => setStatus('open')}
                >
                  Open
                </button>
                <button
                  type="button"
                  className="pill"
                  aria-pressed={status === 'closed'}
                  onClick={() => setStatus('closed')}
                >
                  Closed
                </button>
              </div>
            </div>
            {status === 'closed' && (
              <>
                <div>
                  <label htmlFor="qc-closed">Closed at</label>
                  <input
                    id="qc-closed"
                    type="datetime-local"
                    value={closedAt}
                    onChange={(e) => setClosedAt(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="qc-result">Result (manual)</label>
                  <select
                    id="qc-result"
                    value={result}
                    onChange={(e) => setResult(e.target.value as TradeResult | '')}
                  >
                    <option value="">Not set</option>
                    <option value="win">Win</option>
                    <option value="loss">Loss</option>
                    <option value="breakeven">Breakeven</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="qc-exit">Exit price (optional)</label>
                  <input
                    id="qc-exit"
                    type="number"
                    step="any"
                    value={exitPrice}
                    onChange={(e) => setExitPrice(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="qc-pnl">P&L (manual, optional)</label>
                  <input
                    id="qc-pnl"
                    type="number"
                    step="any"
                    value={userPnl}
                    onChange={(e) => setUserPnl(e.target.value)}
                  />
                </div>
                <div className="full">
                  <label htmlFor="qc-result-note">Result note</label>
                  <input
                    id="qc-result-note"
                    value={resultNote}
                    onChange={(e) => setResultNote(e.target.value)}
                    placeholder="Optional context about the outcome"
                  />
                </div>
              </>
            )}
            <div className="full">
              <label htmlFor="qc-screenshot">Screenshot path (optional)</label>
              <input
                id="qc-screenshot"
                value={screenshotPath}
                onChange={(e) => setScreenshotPath(e.target.value)}
                placeholder="Absolute path to an image inside a permitted directory"
              />
              <p className="hint">
                Screenshots are served only from directories the server permits
                (configured via its launch script). See Settings for guidance.
              </p>
            </div>
            <div className="full">
              <label htmlFor="qc-thesis">Thesis</label>
              <textarea
                id="qc-thesis"
                value={thesis}
                onChange={(e) => setThesis(e.target.value)}
                placeholder="Why you took this trade (optional)"
              />
            </div>
            <div className="full">
              <label htmlFor="qc-notes">Notes</label>
              <textarea
                id="qc-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Anything else worth remembering (optional)"
              />
            </div>
          </div>
          {formError && (
            <p className="error-text" role="alert">
              {formError}
            </p>
          )}
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving…' : 'Capture trade'}
            </button>
          </div>
        </form>
      </Panel>
      {created && (
        <Panel title="Trade saved" accent>
          <p className="muted">
            Trade #{created.id} ({created.symbol_label}) is recorded.
            {created.xp_awarded > 0 && (
              <> The server awarded {created.xp_awarded} XP for this capture.</>
            )}
          </p>
          <div className="row">
            <Link className="btn" to={`/trades/${created.id}`}>
              Open trade details
            </Link>
            <Link className="btn" to="/quick-review">
              Write a Quick Review
            </Link>
          </div>
        </Panel>
      )}
    </>
  )
}
