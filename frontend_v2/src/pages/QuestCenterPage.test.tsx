/**
 * Quest Center integration: real quest data, Claim only when claimable,
 * claim hits the backend endpoint, duplicate submission prevented while
 * pending, and already-claimed/undecided handled with clear feedback.
 */
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuestCenterPage from './QuestCenterPage'
import { renderWithProviders } from '../test/render'
import { FetchMock } from '../test/mockApi'
import { quest } from '../test/fixtures'

function install(quests: ReturnType<typeof quest>[]) {
  const mock = new FetchMock(({ method, url }) => {
    if (url.pathname === '/api/quests' && method === 'GET')
      return { json: { items: quests } }
    if (url.pathname === '/api/quests/JM-01/claim' && method === 'POST')
      return {
        json: { awarded_xp: 50, level_up: null, quest: quest('JM-01', { claimed_at: '2026-10-01T10:00:00', claimable: false }) },
      }
    if (url.pathname === '/api/preferences') return { json: { items: {} } }
    if (url.pathname === '/api/dashboard') return { json: {} }
    if (url.pathname === '/api/xp') return { json: {} }
    if (url.pathname === '/api/achievements') return { json: { items: [] } }
    return undefined
  })
  mock.install()
  return mock
}

describe('QuestCenterPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows real backend progress and no claim button for incomplete quests', async () => {
    install([quest('JM-01', { progress_current: 3, target: 10 })])
    renderWithProviders(<QuestCenterPage />)
    expect(await screen.findByText('3 / 10')).toBeVisible()
    expect(screen.getByText('Quest JM-01')).toBeVisible()
    expect(screen.queryByRole('button', { name: /claim reward/i })).toBeNull()
  })

  it('shows Claim only for claimable quests and calls the backend claim endpoint', async () => {
    const mock = install([quest('JM-01', { claimable: true, completed_at: '2026-09-30T10:00:00' })])
    renderWithProviders(<QuestCenterPage />)
    const claimButton = await screen.findByRole('button', { name: /claim reward/i })
    await act(async () => {
      claimButton.click()
    })
    await waitFor(() =>
      expect(mock.calls.some((c) => c.method === 'POST' && c.path === '/api/quests/JM-01/claim')).toBe(
        true,
      ),
    )
    // backend-confirmed XP feedback appears
    expect(await screen.findByText('+50 XP — Quest reward — Quest JM-01')).toBeVisible()
  })

  it('prevents duplicate claim submissions while a claim is pending', async () => {
    // Wrapper object so TypeScript keeps the declared type across closures.
    const pending: { release: (() => void) | null } = { release: null }
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === '/api/quests' && method === 'GET')
        return { json: { items: [quest('JM-01', { claimable: true, completed_at: '2026-09-30T10:00:00' })] } }
      if (url.pathname === '/api/quests/JM-01/claim' && method === 'POST') {
        return new Promise((resolve) => {
          pending.release = () => resolve({ json: { awarded_xp: 50, level_up: null, quest: {} } })
        }) as never
      }
      if (url.pathname === '/api/preferences') return { json: { items: {} } }
      return undefined
    })
    mock.install()
    renderWithProviders(<QuestCenterPage />)
    const claimButton = await screen.findByRole('button', { name: /claim reward/i })
    await act(async () => {
      claimButton.click()
    })
    // While pending, the button is disabled and shows the pending label.
    await waitFor(() => expect(claimButton).toBeDisabled())
    expect(screen.getByText('Claiming…')).toBeVisible()
    const claimsBefore = mock.calls.filter(
      (c) => c.method === 'POST' && c.path === '/api/quests/JM-01/claim',
    ).length
    await act(async () => {
      claimButton.click()
    })
    expect(
      mock.calls.filter((c) => c.method === 'POST' && c.path === '/api/quests/JM-01/claim').length,
    ).toBe(claimsBefore)
    pending.release?.()
  })

  it('handles already-claimed quests with a clear non-alarming message', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === '/api/quests' && method === 'GET')
        return { json: { items: [quest('JM-01', { claimable: true, completed_at: '2026-09-30T10:00:00' })] } }
      if (url.pathname === '/api/quests/JM-01/claim' && method === 'POST')
        return { status: 409, json: { detail: 'Quest JM-01 was already claimed' } }
      if (url.pathname === '/api/preferences') return { json: { items: {} } }
      return undefined
    })
    mock.install()
    renderWithProviders(<QuestCenterPage />)
    const claimButton = await screen.findByRole('button', { name: /claim reward/i })
    await act(async () => {
      claimButton.click()
    })
    expect(await screen.findByText('Quest JM-01 was already claimed')).toBeVisible()
  })

  it('never shows an invented reward for undecided (null) rewards', async () => {
    install([quest('CN-01', { reward_xp: null, completed_at: '2026-09-30T10:00:00', opt_in: true, category: 'consistency' })])
    renderWithProviders(<QuestCenterPage />)
    expect(await screen.findByText('Reward undecided')).toBeVisible()
    expect(screen.queryByText(/50 XP/)).toBeNull()
    expect(screen.queryByRole('button', { name: /claim reward/i })).toBeNull()
  })

  it('displays deferred quests as not yet available without a claim action', async () => {
    install([quest('LQ-02', { status: 'deferred' })])
    renderWithProviders(<QuestCenterPage />)
    const badges = await screen.findAllByText('Not yet available')
    expect(badges.length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByRole('button', { name: /claim reward/i })).toBeNull()
  })
})
