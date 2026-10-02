/**
 * Trade selector for the review workflows - lists persisted trades from the
 * backend and reports the chosen trade id upward.
 */
import { useTrades } from '../api/hooks'
import type { Trade } from '../api/types'
import { formatDateTime } from '../utils/format'
import { EmptyState, ErrorState, LoadingState } from './states'

const TRADE_OPTIONS = { page_size: 100 } as const

export function TradePicker({
  selectedId,
  onSelect,
  label = 'Trade',
}: {
  selectedId: number | null
  onSelect: (id: number) => void
  label?: string
}) {
  const { data, isPending, isError, error, refetch } = useTrades(TRADE_OPTIONS)

  if (isPending) return <LoadingState label="Loading trades…" />
  if (isError) return <ErrorState message={error.message} onRetry={() => void refetch()} />
  if (!data || data.rows.length === 0) {
    return (
      <EmptyState
        title="No trades recorded yet"
        description="Capture your first executed trade, then come back to review it."
      />
    )
  }

  return (
    <div>
      <label htmlFor="trade-picker">{label}</label>
      <select
        id="trade-picker"
        value={selectedId ?? ''}
        onChange={(e) => onSelect(Number(e.target.value))}
      >
        <option value="" disabled>
          Select a trade…
        </option>
        {data.rows.map((t: Trade) => (
          <option key={t.id} value={t.id}>
            #{t.id} · {t.symbol_label}
            {t.direction ? ` · ${t.direction}` : ''} · {formatDateTime(t.opened_at)}
            {t.status === 'open' ? ' · open' : ''}
          </option>
        ))}
      </select>
      <p className="hint">
        Showing the most recent {data.rows.length} of {data.total} trades.
      </p>
    </div>
  )
}
