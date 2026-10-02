/**
 * Navigation tests: every required page loads through the real router,
 * the active nav state is correct, and unknown routes are handled.
 */
import { act, screen, within } from '@testing-library/react'
import App from './App'
import { renderWithProviders } from './test/render'
import { FetchMock } from './test/mockApi'
import { achievement, emptyDashboard, quest, settingsList, trade, tradeList } from './test/fixtures'

const REQUIRED_PAGES = [
  { path: '/', heading: 'Quest Hub' },
  { path: '/trades', heading: 'Trade Journal' },
  { path: '/quick-capture', heading: 'Quick Capture' },
  { path: '/quick-review', heading: 'Quick Review' },
  { path: '/deep-review', heading: 'Deep Review' },
  { path: '/emotional', heading: 'Emotional Journal' },
  { path: '/daily-review', heading: 'Daily Review' },
  { path: '/weekly-review', heading: 'Weekly Review' },
  { path: '/quests', heading: 'Quest Center' },
  { path: '/achievements', heading: 'Achievements' },
  { path: '/settings', heading: 'Settings' },
]

export function installDefaultApi() {
  const mock = new FetchMock(({ url }) => {
    if (url.pathname === '/api/dashboard') return { json: emptyDashboard }
    if (url.pathname === '/api/quests') return { json: { items: [quest('FT-01')] } }
    if (url.pathname === '/api/achievements')
      return { json: { items: [achievement('ACH-INIT-TRADE')] } }
    if (url.pathname.startsWith('/api/settings/')) return { json: settingsList([]) }
    if (url.pathname === '/api/preferences') return { json: { items: {} } }
    if (url.pathname === '/api/trades') return { json: tradeList([trade(1)]) }
    if (url.pathname === '/api/xp') return { json: emptyDashboard.pilot }
    return undefined
  })
  mock.install()
  return mock
}

async function findHeading(text: string) {
  try {
    return await screen.findByRole('heading', { name: new RegExp(`^${text}`, 'i'), level: 1 })
  } catch {
    return null
  }
}

describe('application navigation', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('renders all required navigation items and each route resolves to its page', async () => {
    installDefaultApi()
    renderWithProviders(<App />)

    const nav = screen.getByRole('navigation', { name: 'Primary' })

    for (const page of REQUIRED_PAGES) {
      expect(
        within(nav).getByRole('link', { name: new RegExp(`^${page.heading}$`) }),
      ).toBeInTheDocument()
    }

    for (const page of REQUIRED_PAGES) {
      const link = within(nav).getByRole('link', { name: new RegExp(`^${page.heading}$`) })
      await act(async () => {
        link.click()
      })
      const heading = await findHeading(page.heading)
      expect(heading).not.toBeNull()
    }
  })

  it('marks the current page as active in the navigation', async () => {
    installDefaultApi()
    renderWithProviders(<App />)
    const nav = screen.getByRole('navigation', { name: 'Primary' })
    const tradesLink = within(nav).getByRole('link', { name: /^Trade Journal$/ })
    await act(async () => {
      tradesLink.click()
    })
    expect(await findHeading('Trade Journal')).not.toBeNull()
    expect(tradesLink).toHaveClass('active')
  })

  it('handles unknown routes gracefully', async () => {
    installDefaultApi()
    renderWithProviders(<App />, { route: '/this/does/not/exist' })
    expect(await findHeading('Unknown route')).not.toBeNull()
  })
})
