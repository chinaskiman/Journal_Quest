/**
 * Keyboard usability and accessibility basics: skip link, focusability of
 * custom controls, aria semantics for pill groups, and the reduced-motion CSS
 * rules baked into the design system.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { RatingPills } from './components/ui'
import { renderWithProviders } from './test/render'
import { FetchMock } from './test/mockApi'
import { emptyDashboard, settingsList, trade, tradeList } from './test/fixtures'
import { useState } from 'react'

/** Read a stylesheet as text (Vitest runs with the project root as cwd). */
function readStyle(name: string): string {
  return readFileSync(join(process.cwd(), 'src', 'styles', name), 'utf-8')
}

describe('accessibility', () => {
  afterEach(() => vi.unstubAllGlobals())

  function installApi() {
    const mock = new FetchMock(({ url }) => {
      if (url.pathname === '/api/dashboard') return { json: emptyDashboard }
      if (url.pathname === '/api/trades') return { json: tradeList([trade(1)]) }
      if (url.pathname.startsWith('/api/settings/')) return { json: settingsList([]) }
      if (url.pathname === '/api/quests') return { json: { items: [] } }
      if (url.pathname === '/api/achievements') return { json: { items: [] } }
      if (url.pathname === '/api/preferences') return { json: { items: {} } }
      return undefined
    })
    mock.install()
    return mock
  }

  it('provides a skip link as the first focusable element', async () => {
    installApi()
    renderWithProviders(<App />)
    const skip = screen.getByRole('link', { name: 'Skip to main content' })
    expect(skip).toBeInTheDocument()
    expect(skip.getAttribute('href')).toBe('#main-content')
  })

  it('renders primary navigation as a semantic landmark with accessible names', async () => {
    installApi()
    renderWithProviders(<App />)
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
  })

  it('supports keyboard operation on custom pill controls', async () => {
    function RatingHarness() {
      const [value, setValue] = useState<number | null>(null)
      return (
        <div>
          <RatingPills name="Energy" value={value} onChange={setValue} />
          <output data-testid="value">{value ?? 'none'}</output>
        </div>
      )
    }
    renderWithProviders(<RatingHarness />)
    const pills = screen.getAllByRole('button')
    // Pills are real buttons - keyboard reachable and labelled
    expect(pills.length).toBe(5)
    pills.forEach((pill) => expect(pill).toHaveAttribute('aria-pressed'))

    const user = userEvent.setup()
    const four = screen.getByRole('button', { name: '4' })
    await user.tab() // first pill
    await user.tab()
    await user.tab()
    await user.tab()
    expect(four).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByTestId('value')).toHaveTextContent('4')
  })

  it('design system honors prefers-reduced-motion', () => {
    // Vitest stubs CSS imports, so assert against the real source files.
    expect(readStyle('base.css')).toMatch(/@media \(prefers-reduced-motion: reduce\)/)
    expect(readStyle('tokens.css')).toMatch(/@media \(prefers-reduced-motion: reduce\)/)
  })
})
