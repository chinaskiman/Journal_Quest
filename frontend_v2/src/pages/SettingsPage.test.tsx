/**
 * Settings integration: CRUD via the real endpoints, backend errors shown,
 * historical-label preservation messaging, and the consistency preference.
 */
import { act, fireEvent, screen } from '@testing-library/react'
import SettingsPage from './SettingsPage'
import { renderWithProviders } from '../test/render'
import { FetchMock } from '../test/mockApi'
import { setting, settingsList } from '../test/fixtures'

/** Fill a controlled React input the way a user would. */
function typeInto(el: HTMLElement, value: string) {
  fireEvent.change(el, { target: { value } })
}

describe('SettingsPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists items from the backend and adds new ones through the API', async () => {
    const mock = new FetchMock(({ method, url, body }) => {
      if (url.pathname === '/api/settings/symbols' && method === 'GET')
        return { json: settingsList([setting(1, 'XAUUSD')]) }
      if (url.pathname === '/api/settings/symbols' && method === 'POST')
        return { status: 201, json: setting(2, body.name) }
      if (url.pathname === '/api/preferences') return { json: { items: {} } }
      return undefined
    })
    mock.install()
    renderWithProviders(<SettingsPage />)
    expect(await screen.findByText('XAUUSD')).toBeVisible()

    const input = screen.getByLabelText('New Symbols name')
    typeInto(input, 'EURUSD')
    await act(async () => {
      screen.getByRole('button', { name: 'Add' }).click()
    })
    const call = mock.calls.find(
      (c) => c.method === 'POST' && c.path === '/api/settings/symbols',
    )
    expect(call?.body).toEqual({ name: 'EURUSD' })
  })

  it('shows backend errors (e.g. duplicate name) clearly', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === '/api/settings/symbols' && method === 'GET')
        return { json: settingsList([]) }
      if (url.pathname === '/api/settings/symbols' && method === 'POST')
        return { status: 409, json: { detail: "'EURUSD' already exists" } }
      if (url.pathname === '/api/preferences') return { json: { items: {} } }
      return undefined
    })
    mock.install()
    renderWithProviders(<SettingsPage />)
    const input = await screen.findByLabelText('New Symbols name')
    typeInto(input, 'EURUSD')
    await act(async () => {
      screen.getByRole('button', { name: 'Add' }).click()
    })
    expect(await screen.findByText("'EURUSD' already exists")).toBeVisible()
  })

  it('renames via the backend and states that history keeps original labels', async () => {
    const mock = new FetchMock(({ method, url, body }) => {
      if (url.pathname === '/api/settings/symbols' && method === 'GET')
        return { json: settingsList([setting(1, 'XAUUSD')]) }
      if (url.pathname === '/api/settings/symbols/1' && method === 'PATCH')
        return { json: setting(1, body.name) }
      if (url.pathname === '/api/preferences') return { json: { items: {} } }
      return undefined
    })
    mock.install()
    renderWithProviders(<SettingsPage />)
    await screen.findByText('XAUUSD')
    await act(async () => {
      screen.getByRole('button', { name: 'Rename' }).click()
    })
    const renameInput = await screen.findByLabelText('Rename')
    typeInto(renameInput, 'GOLD')
    await act(async () => {
      screen.getByRole('button', { name: 'Save' }).click()
    })
    const call = mock.calls.find((c) => c.method === 'PATCH' && c.path === '/api/settings/symbols/1')
    expect(call?.body).toEqual({ name: 'GOLD' })
    expect(
      await screen.findByText('Renamed. Existing journal records keep their original label.'),
    ).toBeVisible()
  })

  it('toggles the consistency-quest preference through the preferences API', async () => {
    const mock = new FetchMock(({ method, url }) => {
      if (url.pathname === '/api/settings/symbols') return { json: settingsList([]) }
      if (url.pathname === '/api/preferences' && method === 'GET')
        return { json: { items: {} } }
      if (url.pathname === '/api/preferences/consistency_quests_enabled' && method === 'PUT')
        return { json: { key: 'consistency_quests_enabled', stored: true } }
      return undefined
    })
    mock.install()
    renderWithProviders(<SettingsPage />)
    await act(async () => {
      screen.getByRole('tab', { name: 'Options' }).click()
    })
    const toggle = await screen.findByRole('button', { name: 'Enable consistency quests' })
    await act(async () => {
      toggle.click()
    })
    const call = mock.calls.find(
      (c) => c.method === 'PUT' && c.path === '/api/preferences/consistency_quests_enabled',
    )
    // The backend takes the value JSON-encoded inside the request body.
    expect(call?.body).toEqual({ value: 'true' })
  })
})

