/**
 * Quick Capture integration: manual-only P&L, backend-authoritative
 * validation, duplicate-submit prevention, and response-driven XP feedback.
 */
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import QuickCapturePage from './QuickCapturePage'
import { renderWithProviders } from '../test/render'
import { FetchMock } from '../test/mockApi'
import { setting, settingsList } from '../test/fixtures'

function install() {
  const mock = new FetchMock(({ method, url }) => {
    if (url.pathname === '/api/settings/symbols')
      return { json: settingsList([setting(1, 'XAUUSD')]) }
    if (url.pathname === '/api/settings/setups')
      return { json: settingsList([setting(1, 'Breakout')]) }
    if (url.pathname === '/api/trades' && method === 'POST')
      return {
        status: 201,
        json: { id: 7, symbol_label: 'XAUUSD', xp_awarded: 20, level_up: null },
      }
    return undefined
  })
  mock.install()
  return mock
}

function select(id: string, value: string) {
  fireEvent.change(document.getElementById(id)!, { target: { value } })
}


describe('QuickCapturePage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('submits manual P&L verbatim and shows server-confirmed XP', async () => {
    const mock = install()
    renderWithProviders(<QuickCapturePage />)
    await screen.findByText('Record an executed trade')

    await act(async () => {
      select('qc-symbol', 'XAUUSD')
    })
    // mark the trade as closed and enter a manual result + P&L
    await act(async () => {
      screen.getByRole('button', { name: 'Closed' }).click()
    })
    const pnlInput = await screen.findByLabelText('P&L (manual, optional)')
    await act(async () => {
      fireEvent.change(pnlInput, { target: { value: '123.45' } })
    })
    await act(async () => {
      select('qc-result', 'win')
    })

    await act(async () => {
      screen.getByRole('button', { name: 'Capture trade' }).click()
    })

    const call = await waitFor(() => {
      const found = mock.calls.find((c) => c.method === 'POST' && c.path === '/api/trades')
      expect(found).toBeDefined()
      return found!
    })
    // P&L is passed through as a manual number, never computed
    expect(call.body.user_pnl).toBe(123.45)
    expect(call.body.result).toBe('win')
    expect(call.body.symbol).toBe('XAUUSD')
    // XP feedback comes from the response only
    expect(await screen.findByText('+20 XP — Quick Capture')).toBeVisible()
    expect(await screen.findByText(/server awarded 20 XP/)).toBeVisible()
  })

  it('blocks submission without required fields (client pre-check)', async () => {
    install()
    renderWithProviders(<QuickCapturePage />)
    await screen.findByText('Record an executed trade')
    await act(async () => {
      screen.getByRole('button', { name: 'Capture trade' }).click()
    })
    expect(await screen.findByText('Symbol is required.')).toBeVisible()
  })

  it('shows the backend validation message when the server rejects', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === '/api/settings/symbols') return { json: settingsList([setting(1, 'XAUUSD')]) }
      if (url.pathname === '/api/settings/setups') return { json: settingsList([]) }
      if (url.pathname === '/api/trades' && method === 'POST')
        return { status: 422, json: { detail: "Symbol 'XAUUSD' is not in Settings." } }
      return undefined
    })
    mock.install()
    renderWithProviders(<QuickCapturePage />)
    await screen.findByText('Record an executed trade')
    await act(async () => {
      select('qc-symbol', 'XAUUSD')
    })
    await act(async () => {
      screen.getByRole('button', { name: 'Capture trade' }).click()
    })
    expect(await screen.findByText("Symbol 'XAUUSD' is not in Settings.")).toBeVisible()
  })

  it('disables the submit button while a capture is pending (no duplicates)', async () => {
    // Wrapper object so TypeScript keeps the declared type across closures.
    const pending: { release: (() => void) | null } = { release: null }
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === '/api/settings/symbols') return { json: settingsList([setting(1, 'XAUUSD')]) }
      if (url.pathname === '/api/settings/setups') return { json: settingsList([]) }
      if (url.pathname === '/api/trades' && method === 'POST')
        return new Promise((resolve) => {
          pending.release = () => resolve({ status: 201, json: { id: 1, xp_awarded: 20, level_up: null } })
        }) as never
      return undefined
    })
    mock.install()
    renderWithProviders(<QuickCapturePage />)
    await screen.findByText('Record an executed trade')
    await act(async () => {
      select('qc-symbol', 'XAUUSD')
    })
    const submit = screen.getByRole('button', { name: 'Capture trade' })
    await act(async () => {
      submit.click()
    })
    await waitFor(() => expect(submit).toBeDisabled())
    expect(screen.getByText('Saving…')).toBeVisible()
    const posts = mock.calls.filter((c) => c.method === 'POST').length
    await act(async () => {
      submit.click()
    })
    expect(mock.calls.filter((c) => c.method === 'POST').length).toBe(posts)
    pending.release?.()
  })
})
