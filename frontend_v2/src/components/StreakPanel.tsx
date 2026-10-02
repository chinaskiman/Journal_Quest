/**
 * Streak Break & Recovery panel for the Quest Hub.
 *
 * Everything rendered here comes from the persisted streak state returned by the
 * backend - nothing is computed or simulated on the client.  Copy is supportive
 * and non-punitive: a broken streak never costs XP and never mentions trading.
 */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'
import type { StreakEvent, StreakState } from '../api/types'
import { Panel, ProgressBar } from './ui'

const STAGE_COPY: Record<StreakEvent['stage'], string> = {
  detected: 'Reflection Quest ready',
  reflection_done: 'Recovery Quest in progress',
  recovery_done: 'Reflection and recovery complete',
  badge_unlocked: 'Recovery complete — badge unlocked',
}

export function StreakPanel({ streak }: { streak: StreakState }) {
  const qc = useQueryClient()
  const [obstacle, setObstacle] = useState('')
  const [resumeStep, setResumeStep] = useState('')

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['dashboard'] })
    void qc.invalidateQueries({ queryKey: ['quests'] })
    void qc.invalidateQueries({ queryKey: ['achievements'] })
  }

  const dismiss = useMutation({
    mutationFn: () => api.markStreakAlertSeen(),
    onSuccess: refresh,
  })

  const saveReflection = useMutation({
    mutationFn: () =>
      api.saveStreakReflection({ obstacle, resume_step: resumeStep }),
    onSuccess: refresh,
  })

  if (!streak.enabled) {
    return (
      <Panel title="Journaling streak">
        <p className="muted" style={{ marginTop: 0 }}>
          Streak tracking is paused. Nothing new is being recorded, and
          everything you have already earned is kept exactly as it is. You can
          turn it back on in Settings at any time.
        </p>
      </Panel>
    )
  }

  const event = streak.active_event
  const showAlert = event !== null && event.alert_seen_at === null
  const reflectionError =
    saveReflection.error instanceof ApiError
      ? saveReflection.error.message
      : saveReflection.error?.message

  return (
    <Panel title="Journaling streak" accent>
      <p className="muted" style={{ marginTop: 0 }}>
        <strong className="num">{streak.current_streak}</strong> day
        {streak.current_streak === 1 ? '' : 's'} in a row. A day counts when you
        complete a Daily or Weekly Review, a Quick or Deep Review, a lesson, or
        an emotional entry. Logging trades does not count.
      </p>

      {showAlert && event && (
        <div
          role="status"
          aria-live="polite"
          className="panel streak-alert"
          style={{ marginBottom: '1rem' }}
        >
          <h3 style={{ marginTop: 0 }}>Your streak has ended</h3>
          <p style={{ marginTop: 0 }}>
            You journaled on{' '}
            <strong className="num">{event.streak_length}</strong> consecutive
            days, then took a break. That happens — and nothing has been lost:
            your XP, quests and badges are all exactly where you left them.
            Whenever you are ready, you can start building consistency again.
          </p>
          <p className="faint num" style={{ marginBottom: '0.6rem' }}>
            Last active day {event.broke_on} · noticed {event.detected_on}
          </p>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => dismiss.mutate()}
            disabled={dismiss.isPending}
          >
            Got it — show me how to restart
          </button>
        </div>
      )}
      {event && (
        <div style={{ marginTop: '1rem' }}>
          <p style={{ marginBottom: '0.5rem' }}>
            <strong>{STAGE_COPY[event.stage]}</strong>
          </p>
          <ProgressBar
            value={event.recovery_current}
            max={event.recovery_target}
            label={`Recovery progress (${event.recovery_current} of ${event.recovery_target} days)`}
          />
          <p className="muted" style={{ marginTop: '0.6rem' }}>
            Recovery counts {event.recovery_target} days of journaling or
            learning after {event.detected_on}, at your own pace. Trading is
            never part of it, and you do not need to be active every day.
          </p>

          {!event.reflection_done && (
            <fieldset style={{ marginTop: '1rem' }}>
              <legend>Reflection Quest (RC-01)</legend>
              <p className="muted" style={{ marginTop: 0 }}>
                Optional, and only as much as you want to share. Saving this
                completes RC-01 for 25 XP.
              </p>
              <label className="field">
                <span>What got in the way of your journaling routine?</span>
                <textarea
                  value={obstacle}
                  onChange={(e) => setObstacle(e.target.value)}
                  rows={2}
                />
              </label>
              <label className="field">
                <span>What is one small thing that could help you resume?</span>
                <textarea
                  value={resumeStep}
                  onChange={(e) => setResumeStep(e.target.value)}
                  rows={2}
                />
              </label>
              {reflectionError && (
                <p className="error-text" role="alert">
                  {reflectionError}
                </p>
              )}
              <button
                type="button"
                className="btn btn-gold"
                onClick={() => saveReflection.mutate()}
                disabled={saveReflection.isPending}
              >
                Save reflection
              </button>
            </fieldset>
          )}

          {event.reflection_done && event.reflection && (
            <div className="panel" style={{ marginTop: '1rem' }}>
              <strong>Your reflection</strong>
              {event.reflection.obstacle && (
                <p className="muted">
                  Got in the way: {event.reflection.obstacle}
                </p>
              )}
              {event.reflection.resume_step && (
                <p className="muted">
                  Small step: {event.reflection.resume_step}
                </p>
              )}
              <p className="faint" style={{ marginBottom: 0 }}>
                You can edit this any time — it will not award XP again.
              </p>
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}