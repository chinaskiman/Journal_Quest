/**
 * Streak Break & Recovery - Quest Hub panel.
 *
 * All props come from the backend payload; these tests verify the supportive
 * (never punitive) messaging, the alert/dismiss flow and the reflection form.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StreakPanel } from './StreakPanel'
import { api } from '../api/client'
import type { StreakEvent, StreakState } from '../api/types'

function wrap(node: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={qc}>{node}</QueryClientProvider>,
  )
}

const baseState: StreakState = {
  enabled: true,
  baseline: '2026-03-01',
  current_streak: 0,
  min_days: 3,
  recovery_target: 2,
  active_event: null,
  message: null,
}

function event(overrides: Partial<StreakEvent> = {}): StreakEvent {
  return {
    id: 1,
    broke_on: '2026-03-03',
    detected_on: '2026-03-05',
    streak_length: 3,
    stage: 'detected',
    reflection_done: false,
    recovery_target: 2,
    recovery_current: 0,
    recovery_done: false,
    recovery_days: [],
    alert_seen_at: null,
    reflection: null,
    as_of: '2026-03-05',
    ...overrides,
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('StreakPanel', () => {
  it('shows the current streak and explains what counts as an active day', () => {
    wrap(<StreakPanel streak={{ ...baseState, current_streak: 4 }} />)
    expect(screen.getByText('4')).toBeTruthy()
    expect(screen.getByText(/Logging trades does not count/i)).toBeTruthy()
  })

  it('shows a supportive streak break alert with the previous length', () => {
    wrap(<StreakPanel streak={{ ...baseState, active_event: event() }} />)
    const alert = screen.getByRole('status')
    expect(alert.textContent).toMatch(/Your streak has ended/i)
    expect(alert.textContent).toContain('3')
    expect(alert.textContent).toMatch(/nothing has been lost/i)
    // supportive, never shaming
    expect(alert.textContent).not.toMatch(/fail|lost your|punish|penalt/i)
  })

  it('explains that trade activity does not need to resume', () => {
    wrap(<StreakPanel streak={{ ...baseState, active_event: event() }} />)
    expect(
      screen.getByText(/Trading is never part of it/i),
    ).toBeTruthy()
  })

  it('dismisses the alert idempotently via the API', async () => {
    const spy = vi
      .spyOn(api, 'markStreakAlertSeen')
      .mockResolvedValue(event({ alert_seen_at: '2026-03-05T12:00:00' }))
    wrap(<StreakPanel streak={{ ...baseState, active_event: event() }} />)
    await userEvent.click(
      screen.getByRole('button', { name: /Got it/i }),
    )
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
  })

  it('offers the Reflection Quest form only before it is done', () => {
    const { unmount } = wrap(
      <StreakPanel streak={{ ...baseState, active_event: event() }} />,
    )
    expect(screen.getByText(/What got in the way/i)).toBeTruthy()
    expect(
      screen.getByText(/one small thing that could help you resume/i),
    ).toBeTruthy()
    unmount()

    wrap(
      <StreakPanel
        streak={{
          ...baseState,
          active_event: event({
            reflection_done: true,
            stage: 'reflection_done',
            reflection: { obstacle: 'Busy week', resume_step: 'One review' },
          }),
        }}
      />,
    )
    expect(screen.queryByText(/What got in the way/i)).toBeNull()
    expect(screen.getByText(/Busy week/)).toBeTruthy()
  })

  it('submits the reflection through the API', async () => {
    const spy = vi
      .spyOn(api, 'saveStreakReflection')
      .mockResolvedValue(event({ reflection_done: true }))
    wrap(<StreakPanel streak={{ ...baseState, active_event: event() }} />)
    await userEvent.type(
      screen.getByLabelText(/What got in the way/i),
      'Busy week',
    )
    await userEvent.click(
      screen.getByRole('button', { name: /Save reflection/i }),
    )
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    expect(spy.mock.calls[0][0]).toMatchObject({ obstacle: 'Busy week' })
  })

  it('shows recovery progress against the approved 2-day target', () => {
    wrap(
      <StreakPanel
        streak={{
          ...baseState,
          active_event: event({
            reflection_done: true,
            stage: 'recovery_done',
            recovery_current: 2,
            recovery_done: true,
          }),
        }}
      />,
    )
    // ProgressBar exposes the label via aria-label (role="progressbar"), so query
    // it accessibly rather than as text content.
    const bar = screen.getByRole('progressbar')
    expect(bar.getAttribute('aria-label')).toContain('2 of 2 days')
    expect(bar.getAttribute('aria-valuenow')).toBe('2')
    expect(screen.getByText(/Recovery complete/i)).toBeTruthy()
  })

  it('explains a paused tracker without erasing records', () => {
    wrap(<StreakPanel streak={{ ...baseState, enabled: false }} />)
    expect(screen.getByText(/Streak tracking is paused/i)).toBeTruthy()
    expect(screen.getByText(/kept exactly as it is/i)).toBeTruthy()
  })
})