/**
 * Notification system for REAL backend events only.
 *
 * Invariants (Phase 3 requirements):
 * - toasts fire exclusively from mutation success/error handlers, never from
 *   query refetches or renders, so refreshes cannot duplicate notifications;
 * - an XP toast is shown only when the response `xp_awarded` is > 0;
 * - the level-up overlay is shown only when the response `level_up` is a
 *   non-null object with a numeric level.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { Sparkles, X } from 'lucide-react'
import type { LevelUp, MutationFeedback } from '../api/types'

type ToastKind = 'success' | 'error' | 'info'

interface Toast {
  id: number
  kind: ToastKind
  message: string
}

interface LevelUpState {
  id: number
  level: number
  title: string
}

interface ToastContextValue {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
  /**
   * Show XP + level-up feedback from an actual mutation response.
   * `label` describes what the user did (e.g. "Quick Capture").
   */
  feedback: (response: MutationFeedback, label: string) => void
  achievement: (name: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

const TOAST_TTL = 4500

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [levelUp, setLevelUp] = useState<LevelUpState | null>(null)
  const nextId = useRef(1)

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = nextId.current++
    setToasts((current) => [...current.slice(-4), { id, kind, message }])
    window.setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id))
    }, TOAST_TTL)
  }, [])

  const value = useMemo<ToastContextValue>(
    () => ({
      success: (message) => push('success', message),
      error: (message) => push('error', message),
      info: (message) => push('info', message),
      feedback: (response: MutationFeedback, label: string) => {
        if (response && typeof response.xp_awarded === 'number' && response.xp_awarded > 0) {
          push('success', `+${response.xp_awarded} XP — ${label}`)
        }
        const lu: LevelUp | null | undefined = response?.level_up
        if (lu && typeof lu.level === 'number' && lu.level > 0) {
          setLevelUp({ id: nextId.current++, level: lu.level, title: lu.title ?? '' })
        }
      },
      achievement: (name) => push('info', `Achievement unlocked — ${name}`),
    }),
    [push],
  )

  // Reduced motion: the overlay stays dismissible via keyboard as well.
  useEffect(() => {
    if (!levelUp) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Enter') setLevelUp(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [levelUp])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <span>{t.message}</span>
            <button
              type="button"
              className="toast-dismiss"
              aria-label="Dismiss notification"
              onClick={() => setToasts((current) => current.filter((x) => x.id !== t.id))}
            >
              <X size={14} aria-hidden />
            </button>
          </div>
        ))}
      </div>
      {levelUp && (
        <div
          className="levelup-overlay"
          role="alertdialog"
          aria-modal="false"
          aria-label={`Level ${levelUp.level} reached`}
        >
          <div className="levelup-card">
            <Sparkles size={28} className="levelup-icon" aria-hidden />
            <p className="levelup-eyebrow">Level up</p>
            <p className="levelup-level" aria-label={`Level ${levelUp.level}`}>
              {levelUp.level}
            </p>
            <p className="levelup-title">{levelUp.title}</p>
            <button type="button" className="btn btn-primary" onClick={() => setLevelUp(null)}>
              Continue
            </button>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  )
}
