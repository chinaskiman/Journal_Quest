import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export function ProgressBar({
  value,
  max = 100,
  label,
  gold = false,
}: {
  value: number
  max?: number
  label?: string
  gold?: boolean
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  return (
    <div
      className="progress-track"
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
    >
      <div className={`progress-fill${gold ? ' progress-fill-gold' : ''}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export function StatTile({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="stat-tile">
      <div className="stat-value num">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export function Panel({
  title,
  accent,
  children,
  elevated,
  actions,
}: {
  title?: string
  accent?: boolean
  children: ReactNode
  elevated?: boolean
  actions?: ReactNode
}) {
  return (
    <section className={elevated ? 'panel-elevated' : 'panel'}>
      {(title || actions) && (
        <div className="row spread" style={{ marginBottom: '0.9rem' }}>
          {title && <h2 className="panel-title" style={{ margin: 0 }}>
            {accent && <span className="accent">◈</span>}
            {title}
          </h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

/** Accessible confirmation dialog (focuses the confirm button when opened). */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  danger,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  message: ReactNode
  confirmLabel?: string
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const confirmRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (open) confirmRef.current?.focus()
  }, [open])
  if (!open) return null
  return createPortal(
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel()
      }}
    >
      <div
        className="modal"
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onCancel()
        }}
      >
        <h2>{title}</h2>
        <div className="muted">{message}</div>
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

/** Small segmented rating control (1..5) rendered as toggle pills. */
export function RatingPills({
  name,
  value,
  onChange,
  max = 5,
  allowEmpty = false,
}: {
  name: string
  value: number | null
  onChange: (value: number | null) => void
  max?: number
  allowEmpty?: boolean
}) {
  return (
    <div className="radio-pills" role="group" aria-label={name}>
      {allowEmpty && (
        <button
          type="button"
          className="pill"
          aria-pressed={value === null}
          onClick={() => onChange(null)}
        >
          —
        </button>
      )}
      {Array.from({ length: max }, (_, i) => i + 1).map((n) => (
        <button
          key={n}
          type="button"
          className="pill"
          aria-pressed={value === n}
          onClick={() => onChange(n)}
        >
          {n}
        </button>
      ))}
    </div>
  )
}
