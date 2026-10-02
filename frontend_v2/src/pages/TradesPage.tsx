/**
 * Trade Journal - browse and manage persisted trade records.
 * Server-side filtering (status/symbol/pagination) + clearly-labeled
 * client-side search/sort over the retrieved page.
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTrades, useSettings } from '../api/hooks'
import type { Trade } from '../api/types'
import { formatDateTime, formatNumber } from '../utils/format'
import { Panel } from '../components/ui'
import { EmptyState, ErrorState, LoadingState } from '../components/states'

const PAGE_SIZE = 50

function ResultBadge({ result }: { result: Trade['result'] }) {
  if (!result) return <span className="faint">—</span>
  const cls =
    result === 'win' ? 'badge-success' : result === 'loss' ? 'badge-danger' : 'badge-muted'
  return <span className={`badge ${cls}`}>{result}</span>
}

export default function TradesPage() {
  const [status, setStatus] = useState<'' | 'open' | 'closed'>('')
  const [symbol, setSymbol] = useState('')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<'recent' | 'oldest'>('recent')
  const [page, setPage] = useState(1)
  const symbols = useSettings('symbols')

  const filters = {
    status: status || undefined,
    symbol: symbol || undefined,
    page,
    page_size: PAGE_SIZE,
  }
  const { data, isPending, isError, error, isFetching, refetch } = useTrades(filters)

  const rows = useMemo(() => {
    const list = data?.rows ?? []
    const filtered = search
      ? list.filter((t) =>
          [t.symbol_label, t.setup_label ?? '', t.notes ?? '', t.thesis ?? '']
            .join(' ')
            .toLowerCase()
            .includes(search.toLowerCase()),
        )
      : list
    return sort === 'recent' ? filtered : [...filtered].reverse()
  }, [data, search, sort])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const hasFilters = Boolean(status || symbol || search || sort !== 'recent')

  function clearFilters() {
    setStatus('')
    setSymbol('')
    setSearch('')
    setSort('recent')
    setPage(1)
  }

  return (
    <>
      <div className="topbar">
        <h1>Trade Journal</h1>
        <div className="topbar-actions">
          <Link to="/quick-capture" className="btn btn-primary">
            Quick Capture
          </Link>
        </div>
      </div>

      <Panel>
        <div className="filter-bar">
          <div>
            <label htmlFor="tf-status">Status</label>
            <select
              id="tf-status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as '' | 'open' | 'closed')
                setPage(1)
              }}
            >
              <option value="">All</option>
              <option value="open">Open</option>
              <option value="closed">Closed</option>
            </select>
          </div>
          <div>
            <label htmlFor="tf-symbol">Symbol</label>
            <select
              id="tf-symbol"
              value={symbol}
              onChange={(e) => {
                setSymbol(e.target.value)
                setPage(1)
              }}
            >
              <option value="">All</option>
              {symbols.data?.items.map((s) => (
                <option key={s.id} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ minWidth: 220 }}>
            <label htmlFor="tf-search">Search (current page)</label>
            <input
              id="tf-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Symbol, setup, notes…"
            />
          </div>
          <div>
            <label htmlFor="tf-sort">Sort</label>
            <select
              id="tf-sort"
              value={sort}
              onChange={(e) => setSort(e.target.value as 'recent' | 'oldest')}
            >
              <option value="recent">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label>&nbsp;</label>
            <button type="button" className="btn" onClick={clearFilters} disabled={!hasFilters}>
              Clear filters
            </button>
          </div>
        </div>
        <p className="hint">
          Search and sort apply to the currently loaded page of {data?.total ?? 0} total
          trades; status and symbol filters run on the server.
        </p>
      </Panel>

      <Panel title="Trades" accent>
        {isPending ? (
          <LoadingState label="Loading trades…" />
        ) : isError ? (
          <ErrorState message={error.message} onRetry={() => void refetch()} />
        ) : !data || data.total === 0 ? (
          <EmptyState
            title="No trades recorded yet"
            description="Capture your first executed trade to start your journal."
            action={
              <Link to="/quick-capture" className="btn btn-primary">
                Open Quick Capture
              </Link>
            }
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No trades match this page's filters"
            description="Adjust or clear the filters above."
          />
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Setup</th>
                    <th>Dir</th>
                    <th>Opened</th>
                    <th>Closed</th>
                    <th>Result</th>
                    <th>P&L (manual)</th>
                    <th>Status</th>
                    <th>Shot</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <Link to={`/trades/${t.id}`}>{t.symbol_label}</Link>
                      </td>
                      <td>{t.setup_label ?? '—'}</td>
                      <td>{t.direction ?? '—'}</td>
                      <td>{formatDateTime(t.opened_at)}</td>
                      <td>{t.closed_at ? formatDateTime(t.closed_at) : '—'}</td>
                      <td>
                        <ResultBadge result={t.result} />
                      </td>
                      <td className="num">{t.user_pnl === null ? '—' : formatNumber(t.user_pnl)}</td>
                      <td>
                        <span className={`badge ${t.status === 'open' ? 'badge-cyan' : 'badge-muted'}`}>
                          {t.status}
                        </span>
                      </td>
                      <td>{t.screenshot_path ? '📷' : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="row spread" style={{ marginTop: '0.9rem' }}>
              <span className="faint">
                Page {data.page} of {totalPages} · {data.total} total
                {isFetching ? ' · refreshing…' : ''}
              </span>
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
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </Panel>
    </>
  )
}
