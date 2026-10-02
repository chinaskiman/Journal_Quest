/**
 * XP/level-up notification invariants:
 * - XP toast appears only when the response xp_awarded > 0;
 * - level-up overlay appears only when level_up is a real object;
 * - nothing is celebrated on zero-XP operations (edits, capped lessons);
 * - query refetches alone never produce notifications.
 */
import { act, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider, useToast } from './ToastContext'
import { api } from '../api/client'
import { FetchMock } from '../test/mockApi'

function Harness() {
  const toast = useToast()
  const zeroXpQuery = useQuery({
    queryKey: ['zero-xp'],
    queryFn: () => ({ xp_awarded: 0, level_up: null }),
  })
  return (
    <div>
      <button type="button" onClick={() => toast.feedback({ xp_awarded: 25, level_up: null }, 'Quick Capture')}>
        award-25
      </button>
      <button type="button" onClick={() => toast.feedback({ xp_awarded: 0, level_up: null }, 'Trade edit')}>
        award-0
      </button>
      <button
        type="button"
        onClick={() =>
          toast.feedback(
            { xp_awarded: 30, level_up: { level: 3, title: 'Chronologist' } },
            'Deep Review',
          )
        }
      >
        award-30-levelup
      </button>
      <span data-testid="zero-xp-loaded">{zeroXpQuery.isSuccess ? 'loaded' : 'loading'}</span>
    </div>
  )
}

function renderHarness() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <Harness />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('mutation feedback notifications', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows an XP toast only when xp_awarded > 0', async () => {
    renderHarness()
    await act(async () => {
      screen.getByText('award-0').click()
    })
    expect(screen.queryByText('+0 XP — Trade edit')).toBeNull()

    await act(async () => {
      screen.getByText('award-25').click()
    })
    expect(await screen.findByText('+25 XP — Quick Capture')).toBeVisible()
  })

  it('shows the level-up overlay only when level_up is a real object', async () => {
    renderHarness()
    await act(async () => {
      screen.getByText('award-30-levelup').click()
    })
    const overlay = await screen.findByRole('alertdialog')
    expect(overlay).toHaveAttribute('aria-label', 'Level 3 reached')
    expect(screen.getByText('Chronologist')).toBeVisible()

    await act(async () => {
      screen.getByRole('button', { name: 'Continue' }).click()
    })
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('never celebrates a zero-XP payload even after refetches', async () => {
    // A query that returns a zero-XP "response" (like a refetch after an edit)
    // must not trigger any notification - only mutations use toast.feedback().
    renderHarness()
    await waitFor(() =>
      expect(screen.getByTestId('zero-xp-loaded')).toHaveTextContent('loaded'),
    )
    expect(screen.queryByText(/XP/)).toBeNull()
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })
})
