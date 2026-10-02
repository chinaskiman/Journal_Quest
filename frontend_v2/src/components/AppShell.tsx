/**
 * Application shell: persistent sidebar navigation + adaptive main area.
 * All nav items map to implemented routes (no nonfunctional links).
 */
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  Award,
  BookOpenText,
  CalendarDays,
  CalendarRange,
  ChevronsLeft,
  ChevronsRight,
  ClipboardList,
  Compass,
  HeartPulse,
  ListChecks,
  Plus,
  Rocket,
  ScrollText,
  Settings as SettingsIcon,
  Telescope,
} from 'lucide-react'
import { AchievementWatcher } from './AchievementWatcher'

interface NavItem {
  to: string
  label: string
  icon: ReactNode
}

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Command',
    items: [
      { to: '/', label: 'Quest Hub', icon: <Compass size={18} aria-hidden /> },
      { to: '/trades', label: 'Trade Journal', icon: <BookOpenText size={18} aria-hidden /> },
      { to: '/quick-capture', label: 'Quick Capture', icon: <Plus size={18} aria-hidden /> },
    ],
  },
  {
    label: 'Reflection',
    items: [
      { to: '/quick-review', label: 'Quick Review', icon: <ClipboardList size={18} aria-hidden /> },
      { to: '/deep-review', label: 'Deep Review', icon: <Telescope size={18} aria-hidden /> },
      { to: '/emotional', label: 'Emotional Journal', icon: <HeartPulse size={18} aria-hidden /> },
      { to: '/daily-review', label: 'Daily Review', icon: <CalendarDays size={18} aria-hidden /> },
      { to: '/weekly-review', label: 'Weekly Review', icon: <CalendarRange size={18} aria-hidden /> },
    ],
  },
  {
    label: 'Progression',
    items: [
      { to: '/quests', label: 'Quest Center', icon: <ListChecks size={18} aria-hidden /> },
      { to: '/achievements', label: 'Achievements', icon: <Award size={18} aria-hidden /> },
    ],
  },
  {
    label: 'System',
    items: [{ to: '/settings', label: 'Settings', icon: <SettingsIcon size={18} aria-hidden /> }],
  },
]

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [narrow, setNarrow] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= 1024 : false,
  )

  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth <= 1024)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const isRail = collapsed || narrow

  return (
    <div className={`app${collapsed ? ' collapsed' : ''}${collapsed === false && narrow ? ' manually-expanded' : ''}`}>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <nav className="sidebar" aria-label="Primary">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <Rocket size={20} />
          </span>
          <span className="brand-name">Trade Quest</span>
        </div>
        <div className="nav">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="nav-group-label">{group.label}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                >
                  {item.icon}
                  <span className="nav-label">{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <button
            type="button"
            className="btn btn-sm collapse-btn"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          >
            {collapsed ? <ChevronsRight size={16} aria-hidden /> : <ChevronsLeft size={16} aria-hidden />}
          </button>
        </div>
      </nav>
      <main className="main" id="main-content">
        <Outlet />
      </main>
      <AchievementWatcher />
    </div>
  )
}
