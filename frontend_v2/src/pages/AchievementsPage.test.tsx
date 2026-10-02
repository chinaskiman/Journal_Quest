/**
 * Achievements gallery: locked hidden secrets stay "???"; unlocked items show
 * backend-provided data; no fabricated achievements or XP.
 */
import { screen } from '@testing-library/react'
import AchievementsPage from './AchievementsPage'
import { renderWithProviders } from '../test/render'
import { FetchMock } from '../test/mockApi'
import { achievement } from '../test/fixtures'

describe('AchievementsPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('keeps locked secret achievements hidden and shows unlocked data', async () => {
    const mock = new FetchMock(({ url }) => {
      if (url.pathname === '/api/achievements')
        return {
          json: {
            items: [
              achievement('ACH-INIT-TRADE', {
                unlocked: true,
                unlocked_at: '2026-09-30T18:00:00',
              }),
              achievement('ACH-SECRET-NIGHT', {
                name: '???',
                description: 'Hidden achievement.',
                category: 'secret',
                hidden: true,
                unlocked: false,
              }),
            ],
          },
        }
      return undefined
    })
    mock.install()
    renderWithProviders(<AchievementsPage />)

    // Secret stays hidden - name and description are never revealed
    expect(await screen.findByText('???')).toBeVisible()
    expect(screen.getAllByText('Hidden achievement.').length).toBeGreaterThan(0)
    expect(screen.queryByText('Night Shift')).toBeNull()

    // Unlocked achievement shows its real backend-provided data
    expect(screen.getByText('Achievement ACH-INIT-TRADE')).toBeVisible()
    expect(screen.getByText('Description ACH-INIT-TRADE')).toBeVisible()
    expect(screen.getByText(/Unlocked/)).toBeVisible()

    // No XP is invented for achievements
    expect(screen.queryByText(/XP/)).toBeNull()
  })

  it('offers Mark as seen for unseen unlocks', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === '/api/achievements' && method === 'GET')
        return {
          json: {
            items: [
              achievement('ACH-INIT-TRADE', {
                unlocked: true,
                unlocked_at: '2026-09-30T18:00:00',
                seen_at: null,
              }),
            ],
          },
        }
      if (url.pathname === '/api/achievements/ACH-INIT-TRADE/seen' && method === 'POST')
        return { status: 204 }
      return undefined
    })
    mock.install()
    renderWithProviders(<AchievementsPage />)
    expect(await screen.findByText('New')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Mark as seen' })).toBeVisible()
  })
})
