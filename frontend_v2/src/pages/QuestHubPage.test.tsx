/**
 * Quest Hub level display - regression cover for the XP/level mismatch.
 *
 * The backend sends `next_level_xp_needed` as the XP STILL needed to reach the
 * next level (already net of the XP earned inside the current level) and
 * `progress_pct` as the within-level percentage.  The hub once subtracted
 * `current_level_xp` a second time (492 XP -> "166 XP to level 5" instead of
 * 208) and used `next_level_xp_needed` as the bar's denominator, so the bar
 * hit 100% halfway through every level.  These tests pin the display to the
 * values the server actually sent, at several non-zero in-level positions.
 */
import { screen, waitFor } from '@testing-library/react'
import QuestHubPage from './QuestHubPage'
import { renderWithProviders } from '../test/render'
import { FetchMock } from '../test/mockApi'
import { cumulativeThreshold, dashboardWithXp, pilotForXp } from '../test/fixtures'
import type { XpSummary } from '../api/types'

function install(totalXp: number, pilotOverrides: Partial<XpSummary> = {}) {
  const mock = new FetchMock(({ url }) => {
    if (url.pathname === '/api/dashboard')
      return { json: dashboardWithXp(totalXp, pilotOverrides) }
    if (url.pathname === '/api/xp') return { json: pilotForXp(totalXp, pilotOverrides) }
    if (url.pathname === '/api/quests') return { json: { items: [] } }
    if (url.pathname === '/api/achievements') return { json: { items: [] } }
    return undefined
  })
  mock.install()
  return mock
}

/** The single line that states how much XP is left to the next level. */
function remainingText(): string {
  return screen.getByText(/XP to level/).textContent ?? ''
}

/** Rendered fill width of the pilot progress bar, in percent. */
function barPercent(): number {
  const fill = document.querySelector('.progress-fill') as HTMLElement | null
  const width = fill?.style.width ?? '0%'
  return Number.parseFloat(width)
}

describe('QuestHubPage level display', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the server-provided remaining XP (492 XP -> 208, not 166)', async () => {
    install(492)
    renderWithProviders(<QuestHubPage />)

    // The exact state from the Phase 3 screenshots.
    const pilot = pilotForXp(492)
    expect(pilot.level).toBe(4)
    expect(pilot.current_level_xp).toBe(42)
    expect(pilot.next_level_xp_needed).toBe(208)
    expect(pilot.progress_pct).toBe(16.8)

    expect(await screen.findByText('492 XP total')).toBeVisible()
    expect(remainingText()).toBe('208 XP to level 5')
    // The old expression double-counted in-level XP as 208 - 42.
    expect(remainingText()).not.toBe('166 XP to level 5')
  })

  it('renders the progress bar from the server percentage, not a local ratio', async () => {
    install(492)
    renderWithProviders(<QuestHubPage />)
    const bar = await screen.findByRole('progressbar', { name: 'Progress to next level' })
    await waitFor(() => expect(barPercent()).toBeCloseTo(16.8, 1))
    // The faulty denominator (42 / 208) would have shown ~20.19%.
    expect(barPercent()).not.toBeCloseTo(20.19, 1)
    expect(bar).toHaveAttribute('aria-valuemax', '100')
  })

  it('matches the real first-level case (30 XP -> 70 to level 2)', async () => {
    install(30)
    renderWithProviders(<QuestHubPage />)
    expect(await screen.findByText('30 XP total')).toBeVisible()
    expect(remainingText()).toBe('70 XP to level 2')
    await waitFor(() => expect(barPercent()).toBeCloseTo(30, 1))
  })

  it('handles the mastery tier without inventing a next level', async () => {
    install(20000, { next_level_total_xp: null, progress_pct: 100 })
    renderWithProviders(<QuestHubPage />)
    expect(await screen.findByText('Mastery level reached')).toBeVisible()
    expect(screen.queryByText(/XP to level/)).toBeNull()
  })

  // Boundary sweep: the displayed number and bar must always be the server's.
  const TOTALS = [0, 30, 99, 100, 120, 492, 699, 700, 1000, 1350, 2700]
  it.each(TOTALS)('mirrors the backend payload at %i total XP', async (total) => {
    install(total)
    const { unmount } = renderWithProviders(<QuestHubPage />)

    const pilot = pilotForXp(total)
    const span = 100 + 50 * (pilot.level - 1)
    // Fixture sanity: remaining + in-level must equal the level span.
    expect(pilot.current_level_xp + pilot.next_level_xp_needed).toBe(span)
    expect(pilot.next_level_total_xp).toBe(cumulativeThreshold(pilot.level) + span)

    if (total === 0) {
      // 0 XP still renders the pilot panel (the journal is not empty here).
      expect(await screen.findByText('100 XP to level 2')).toBeVisible()
    } else {
      expect(await screen.findByText(`${pilot.next_level_xp_needed} XP to level ${pilot.level + 1}`))
        .toBeVisible()
    }
    await waitFor(() => expect(barPercent()).toBeCloseTo(pilot.progress_pct, 1))
    unmount()
  })
})
