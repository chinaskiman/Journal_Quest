import { api, ApiError } from './client'
import { FetchMock } from '../test/mockApi'

describe('api client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends typed payloads to the exact backend endpoints', async () => {
    const mock = new FetchMock(({ method, url, body }) => {
      if (method === 'POST' && url.pathname === '/api/trades')
        return { status: 201, json: { id: 1, xp_awarded: 20, level_up: null } }
      if (method === 'POST' && url.pathname === '/api/quests/FT-01/claim')
        return { status: 200, json: { awarded_xp: 25, level_up: null, quest: {} } }
      if (method === 'PUT' && url.pathname === '/api/preferences/consistency_quests_enabled')
        return { status: 200, json: { key: 'consistency_quests_enabled', stored: true } }
      if (method === 'GET' && url.pathname === '/api/trades')
        return { status: 200, json: { rows: [], total: 0, page: 1, page_size: 50 } }
    })
    mock.install()

    await api.createTrade({ symbol: 'EURUSD', opened_at: '2026-10-01T09:00' })
    expect(mock.calls.find((c) => c.path === '/api/trades')?.body).toEqual({
      symbol: 'EURUSD',
      opened_at: '2026-10-01T09:00',
    })

    await api.claimQuest('FT-01')
    expect(mock.calls.some((c) => c.method === 'POST' && c.path === '/api/quests/FT-01/claim')).toBe(
      true,
    )

    await api.putPreference('consistency_quests_enabled', true)
    const prefCall = mock.calls.find((c) => c.path === '/api/preferences/consistency_quests_enabled')
    // backend expects a JSON string inside the request body
    expect(prefCall?.body).toEqual({ value: 'true' })

    await api.listTrades({ status: 'open', page: 2 })
    expect(mock.calls.some((c) => c.path.includes('/api/trades?status=open&page=2'))).toBe(true)
  })

  it('surfaces backend validation details as ApiError', async () => {
    const mock = new FetchMock(() => ({ status: 422, json: { detail: 'Symbol X is not in Settings' } }))
    mock.install()
    await expect(api.createTrade({ symbol: 'X', opened_at: '2026-10-01T09:00' })).rejects.toThrow(
      'Symbol X is not in Settings',
    )
  })

  it('extracts pydantic array details into a readable message', async () => {
    const mock = new FetchMock(() => ({
      status: 422,
      json: { detail: [{ msg: 'Input should be 1..5' }, { msg: 'Field required' }] },
    }))
    mock.install()
    await expect(
      api.createEmotionalEntry({ emotion: 'calm', intensity: 9 }),
    ).rejects.toThrow('Input should be 1..5; Field required')
  })

  it('treats 204 as success with no body', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (method === 'DELETE' && url.pathname === '/api/trades/1') return { status: 204 }
    })
    mock.install()
    await expect(api.deleteTrade(1)).resolves.toBeUndefined()
  })

  it('throws ApiError with status for network-level failures', async () => {
    const mock = new FetchMock(() => ({ status: 404, json: { detail: 'Trade not found' } }))
    mock.install()
    const err = await api.getTrade(99).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(404)
  })
})
