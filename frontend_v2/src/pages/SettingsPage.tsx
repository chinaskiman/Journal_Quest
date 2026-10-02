/**
 * Settings - symbols / setups / emotions managers, consistency-quest
 * preference, screenshot guidance, and local backups.  Historical label
 * snapshots are preserved by the backend; this UI never rewrites history.
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { useInvalidation, useDashboard, usePreferences, useSettings } from '../api/hooks'
import type { SettingListName } from '../api/types'
import { useToast } from '../feedback/ToastContext'
import { ConfirmDialog, Panel } from '../components/ui'
import { ErrorState, LoadingState } from '../components/states'

const LISTS: { key: SettingListName; label: string; help: string }[] = [
  { key: 'symbols', label: 'Symbols', help: 'Instruments you trade.' },
  { key: 'setups', label: 'Setups', help: 'Your trade setups.' },
  { key: 'emotions', label: 'Emotions', help: 'Feelings you track in the Emotional Journal.' },
]

const CONSISTENCY_KEY = 'consistency_quests_enabled'
  const STREAK_KEY = 'streak_tracking_enabled'

export default function SettingsPage() {
  const toast = useToast()
  const invalidate = useInvalidation()
  const [tab, setTab] = useState<SettingListName | 'options'>('symbols')
  const [showInactive, setShowInactive] = useState(false)
  const [newName, setNewName] = useState('')
  const [renaming, setRenaming] = useState<{ id: number; name: string } | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)

  const activeList = LISTS.find((l) => l.key === tab)
  const settings = useSettings(activeList?.key ?? 'symbols', showInactive)
  const preferences = usePreferences()

  const consistencyEnabled = preferences.data?.items[CONSISTENCY_KEY] === true
  // Streak tracking is enabled by default: an absent preference means enabled,
  // mirroring app2.services.streaks.is_enabled on the backend.
  const streakEnabled = preferences.data?.items[STREAK_KEY] !== false
  const dashboard = useDashboard()

  const createMutation = useMutation({
    mutationFn: (name: string) => api.createSetting(activeList!.key, name),
    onSuccess: () => {
      toast.success('Added.')
      invalidate.progress()
      setNewName('')
    },
    onError: (error) => toast.error(error.message),
  })

  const renameMutation = useMutation({
    mutationFn: (payload: { id: number; name: string }) =>
      api.updateSetting(activeList!.key, payload.id, { name: payload.name }),
    onSuccess: () => {
      toast.success('Renamed. Existing journal records keep their original label.')
      invalidate.progress()
      setRenaming(null)
    },
    onError: (error) => toast.error(error.message),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: (payload: { id: number; is_active: boolean }) =>
      api.updateSetting(activeList!.key, payload.id, { is_active: payload.is_active }),
    onSuccess: () => {
      toast.success('Updated. History is never rewritten by this change.')
      invalidate.progress()
    },
    onError: (error) => toast.error(error.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteSetting(activeList!.key, id, false),
    onSuccess: () => {
      toast.success('Archived (soft delete). Past records keep this label.')
      invalidate.progress()
      setDeleting(null)
    },
    onError: (error) => toast.error(error.message),
  })

  const consistencyMutation = useMutation({
    mutationFn: (enabled: boolean) => api.putPreference(CONSISTENCY_KEY, enabled),
    onSuccess: () => {
      invalidate.journal()
    },
    onError: (error) => toast.error(error.message),
  })

  const streakMutation = useMutation({
    mutationFn: (enabled: boolean) => api.putPreference(STREAK_KEY, enabled),
    onSuccess: () => {
      invalidate.progress()
      invalidate.journal()
    },
    onError: (error) => toast.error(error.message),
  })

  const backupMutation = useMutation({
    mutationFn: () => api.createBackup(),
    onSuccess: (result) => toast.success(`Backup created: ${result.backup}`),
    onError: (error) => toast.error(error.message),
  })

  return (
    <>
      <div className="topbar">
        <h1>Settings</h1>
      </div>

      <div className="row" role="tablist" aria-label="Settings sections">
        {LISTS.map((list) => (
          <button
            key={list.key}
            type="button"
            role="tab"
            aria-selected={tab === list.key}
            className="pill"
            aria-pressed={tab === list.key}
            onClick={() => setTab(list.key)}
          >
            {list.label}
          </button>
        ))}
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'options'}
          className="pill"
          aria-pressed={tab === 'options'}
          onClick={() => setTab('options')}
        >
          Options
        </button>
      </div>

      {tab !== 'options' && activeList && (
        <Panel title={activeList.label} accent>
          <p className="muted">{activeList.help}</p>
          <div className="row" style={{ marginBottom: '1rem' }}>
            <input
              style={{ maxWidth: 280 }}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder={`New ${activeList.label.toLowerCase().replace(/s$/, '')} name`}
              aria-label={`New ${activeList.label} name`}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newName.trim()) createMutation.mutate(newName.trim())
              }}
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={!newName.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate(newName.trim())}
            >
              Add
            </button>
            <label className="row" style={{ gap: '0.4rem', marginBottom: 0 }}>
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                style={{ width: 'auto' }}
              />
              Show archived
            </label>
          </div>

          {settings.isPending ? (
            <LoadingState />
          ) : settings.isError ? (
            <ErrorState message={settings.error.message} onRetry={() => void settings.refetch()} />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {settings.data?.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {renaming?.id === item.id ? (
                        <div className="row">
                          <input
                            value={renaming.name}
                            onChange={(e) => setRenaming({ id: item.id, name: e.target.value })}
                            aria-label="Rename"
                          />
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            disabled={!renaming.name.trim() || renameMutation.isPending}
                            onClick={() =>
                              renameMutation.mutate({ id: item.id, name: renaming.name.trim() })
                            }
                          >
                            Save
                          </button>
                          <button type="button" className="btn btn-sm" onClick={() => setRenaming(null)}>
                            Cancel
                          </button>
                        </div>
                      ) : (
                        item.name
                      )}
                    </td>
                    <td>
                      {item.is_active ? (
                        <span className="badge badge-success">Active</span>
                      ) : (
                        <span className="badge badge-muted">Archived</span>
                      )}
                    </td>
                    <td>
                      <div className="row">
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => setRenaming({ id: item.id, name: item.name })}
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() =>
                            toggleActiveMutation.mutate({ id: item.id, is_active: !item.is_active })
                          }
                          disabled={toggleActiveMutation.isPending}
                        >
                          {item.is_active ? 'Disable' : 'Re-enable'}
                        </button>
                        {item.is_active && (
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            onClick={() => setDeleting(item.id)}
                          >
                            Archive
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="hint">
            Renaming or archiving only affects future entries — records already
            written keep their original label snapshot. Archiving (soft delete)
            is always safe; the server refuses destructive deletes while history
            still references a label.
          </p>
        </Panel>
      )}

      {tab === 'options' && (
        <>
          <Panel title="Quests">
            <p className="muted">
              Consistency quests are opt-in and disabled by default. Enabling
              them simply counts the distinct days on which you wrote a Daily
              Review, and their rewards are undecided (so none are displayed).
              Streak tracking — a different, separate feature — is described in
              the panel below.
            </p>
            <button
              type="button"
              className="btn"
              aria-pressed={consistencyEnabled}
              onClick={() => consistencyMutation.mutate(!consistencyEnabled)}
              disabled={consistencyMutation.isPending || preferences.isPending}
            >
              {consistencyMutation.isPending
                ? 'Saving…'
                : consistencyEnabled
                  ? 'Disable consistency quests'
                  : 'Enable consistency quests'}
            </button>
          </Panel>

          <Panel title="Streak tracking">
            <p className="muted">
              Streak tracking is <strong>on by default</strong>. It counts your
              consecutive journaling days — a day counts when you complete a Daily
              or Weekly Review, a Quick or Deep Review, a lesson, or an emotional
              entry. <strong>Trade activity never counts</strong>, and there is
              no daily streak bonus and no penalty.
            </p>
            <p className="muted">
              If a streak of at least {dashboard.data?.streak.min_days ?? 3}{' '}
              days ends, Trade Quest shows a supportive message and offers a
              Reflection Quest and a Recovery Quest to help you restart at your
              own pace. A broken streak never removes XP, quests or badges.
            </p>
            <p className="muted">
              Turning tracking off pauses new streak detection. Everything you
              have already recorded is preserved. Turning it back on starts a
              fresh counting baseline from that day — no past break is generated
              retroactively.
            </p>
            <button
              type="button"
              className="btn"
              aria-pressed={streakEnabled}
              onClick={() => streakMutation.mutate(!streakEnabled)}
              disabled={streakMutation.isPending || preferences.isPending}
            >
              {streakMutation.isPending
                ? 'Saving…'
                : streakEnabled
                  ? 'Turn off streak tracking'
                  : 'Turn on streak tracking'}
            </button>
          </Panel>

          <Panel title="Screenshot directories">
            <p className="muted">
              Screenshots are served only from directories the backend permits,
              configured through the <code>TRADEQUEST2_SCREENSHOT_DIRS</code>{' '}
              environment variable. The Windows launch scripts preset it to your
              Pictures folder; to allow other folders, define the variable
              before launching (separate multiple folders with a semicolon).
              This is a server-side security allow-list — the app never offers
              unrestricted file browsing.
            </p>
          </Panel>

          <Panel title="Backups">
            <p className="muted">
              Create a local backup of your journal database at any time. The
              last 10 backups are retained on disk.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => backupMutation.mutate()}
              disabled={backupMutation.isPending}
            >
              {backupMutation.isPending ? 'Backing up…' : 'Create backup now'}
            </button>
          </Panel>

          <Panel title="About this app">
            <p className="muted" style={{ marginTop: 0 }}>
              Trade Quest is a local-first, single-user journal. It runs entirely
              on your machine, binds only to 127.0.0.1, has no accounts, no
              cloud sync, no telemetry, and no broker integration. It never
              places, suggests, or automates trades.
            </p>
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={deleting !== null}
        title="Archive this entry?"
        message="It will disappear from dropdowns but remain in your history — records keep their original label."
        confirmLabel="Archive"
        busy={deleteMutation.isPending}
        onConfirm={() => deleting !== null && deleteMutation.mutate(deleting)}
        onCancel={() => setDeleting(null)}
      />
    </>
  )
}
