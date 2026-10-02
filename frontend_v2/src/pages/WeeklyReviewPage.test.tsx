/**
 * Weekly Review integration: advice_to_future_me null vs populated, unique
 * per week (server 409 on create when it exists), edit vs create modes, and
 * no XP celebration on edit.
 */
import { act, screen } from '@testing-library/react'
import WeeklyReviewPage from './WeeklyReviewPage'
import { renderWithProviders } from '../test/render'
import { FetchMock } from '../test/mockApi'

const WEEK = '2026-W40'

const savedReview = (advice: string | null) => ({
  json: {
    id: 3,
    iso_year: 2026,
    iso_week: 40,
    highlights: 'Consistent journaling',
    challenges: null,
    patterns: null,
    plan_next_week: null,
    advice_to_future_me: advice,
    created_at: '2026-10-01T10:00:00',
    updated_at: '2026-10-01T10:00:00',
  },
})

describe('WeeklyReviewPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows create mode with an empty advice field for an unwritten week', async () => {
    const mock = new FetchMock(({ url }) => {
      if (url.pathname === `/api/weekly-reviews/${WEEK}`)
        return { status: 404, json: { detail: 'No weekly review for this week' } }
      if (url.pathname === '/api/weekly-reviews')
        return { json: { rows: [], total: 0, page: 1, page_size: 50 } }
      return undefined
    })
    mock.install()
    renderWithProviders(<WeeklyReviewPage />)
    expect(await screen.findByText('New Weekly Review')).toBeVisible()
    expect(screen.getByLabelText('Advice to future me (optional)')).toHaveValue('')
  })

  it('loads a saved review including null advice without inventing content', async () => {
    const mock = new FetchMock(({ url }) => {
      if (url.pathname === `/api/weekly-reviews/${WEEK}`) return savedReview(null)
      if (url.pathname === '/api/weekly-reviews')
        return { json: { rows: [], total: 0, page: 1, page_size: 50 } }
      return undefined
    })
    mock.install()
    renderWithProviders(<WeeklyReviewPage />)
    expect(await screen.findByText('Edit Weekly Review (no XP for edits)')).toBeVisible()
    expect(screen.getByText(/No advice to future you was recorded/)).toBeVisible()
    expect(screen.getByLabelText('Highlights')).toHaveValue('Consistent journaling')
    expect(screen.getByLabelText('Advice to future me (optional)')).toHaveValue('')
  })

  it('populates saved advice when the backend provides it', async () => {
    const mock = new FetchMock(({ url }) => {
      if (url.pathname === `/api/weekly-reviews/${WEEK}`) return savedReview('Rest is part of the process')
      if (url.pathname === '/api/weekly-reviews')
        return { json: { rows: [], total: 0, page: 1, page_size: 50 } }
      return undefined
    })
    mock.install()
    renderWithProviders(<WeeklyReviewPage />)
    await screen.findByText('Edit Weekly Review (no XP for edits)')
    expect(screen.getByLabelText('Advice to future me (optional)')).toHaveValue(
      'Rest is part of the process',
    )
    expect(screen.queryByText(/No advice to future you was recorded/)).toBeNull()
  })

  it('saves via the correct week-scoped endpoint and shows server XP only on create', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === `/api/weekly-reviews/${WEEK}` && method === 'GET')
        return { status: 404, json: { detail: 'No weekly review for this week' } }
      if (url.pathname === `/api/weekly-reviews/${WEEK}` && method === 'POST')
        return {
          status: 201,
          json: {
            id: 9,
            iso_year: 2026,
            iso_week: 40,
            highlights: null,
            challenges: null,
            patterns: null,
            plan_next_week: null,
            advice_to_future_me: null,
            created_at: '2026-10-01T10:00:00',
            updated_at: '2026-10-01T10:00:00',
            xp_awarded: 30,
            level_up: null,
          },
        }
      if (url.pathname === '/api/weekly-reviews')
        return { json: { rows: [], total: 0, page: 1, page_size: 50 } }
      return undefined
    })
    mock.install()
    renderWithProviders(<WeeklyReviewPage />)
    await screen.findByText('New Weekly Review')
    await act(async () => {
      screen.getByRole('button', { name: 'Save Weekly Review' }).click()
    })
    const call = mock.calls.find(
      (c) => c.method === 'POST' && c.path === `/api/weekly-reviews/${WEEK}`,
    )
    expect(call).toBeDefined()
    expect(call!.body).toEqual({
      highlights: null,
      challenges: null,
      patterns: null,
      plan_next_week: null,
      advice_to_future_me: null,
    })
    expect(await screen.findByText('+30 XP — Weekly Review')).toBeVisible()
  })

  it('edits without any XP celebration (backend PATCH returns no XP fields)', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === `/api/weekly-reviews/${WEEK}` && method === 'GET')
        return savedReview(null)
      if (url.pathname === `/api/weekly-reviews/${WEEK}` && method === 'PATCH')
        return savedReview(null)
      if (url.pathname === '/api/weekly-reviews')
        return { json: { rows: [], total: 0, page: 1, page_size: 50 } }
      return undefined
    })
    mock.install()
    renderWithProviders(<WeeklyReviewPage />)
    await screen.findByText('Edit Weekly Review (no XP for edits)')
    await act(async () => {
      screen.getByRole('button', { name: 'Save changes' }).click()
    })
    expect(
      mock.calls.some((c) => c.method === 'PATCH' && c.path === `/api/weekly-reviews/${WEEK}`),
    ).toBe(true)
    expect(await screen.findByText('Weekly Review updated. Edits award no XP.')).toBeVisible()
    expect(screen.queryByText(/XP — Weekly Review/)).toBeNull()
  })
})
