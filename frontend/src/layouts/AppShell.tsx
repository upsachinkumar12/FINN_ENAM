import { Bell, BookOpenText, Layers, MessageCircle, Moon, RotateCw, Search, Sun, SunMoon } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { relTime } from '../utils/format'

const TABS = [
  { to: '/', label: 'Today', icon: BookOpenText, end: true },
  { to: '/feed', label: 'Feed', icon: Layers },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/research', label: 'Research', icon: Search },
  { to: '/ask', label: 'Ask', icon: MessageCircle },
]

export function AppShell() {
  const { refresh, startRefresh, theme, setTheme } = useApp()
  const running = refresh?.state === 'running' || refresh?.state === 'started'
  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : SunMoon
  const nextTheme = theme === 'system' ? 'dark' : theme === 'dark' ? 'light' : 'system'

  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-line bg-page/95 px-4 backdrop-blur">
        <span className="text-[15px] font-bold tracking-tight">FINN</span>
        <span className="truncate text-xs text-ink-3" aria-live="polite">
          {running ? `Updating · ${refresh?.step ?? 'starting'}…` : refresh?.finished_at ? `Data updated ${relTime(refresh.finished_at)}` : 'Not refreshed yet'}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button onClick={() => void startRefresh()} disabled={running} aria-label="Refresh data"
            className="grid size-8 place-items-center rounded-md text-ink-2 hover:bg-surface-2 disabled:opacity-60">
            <RotateCw size={16} className={running ? 'animate-spin' : ''} aria-hidden />
          </button>
          <button onClick={() => setTheme(nextTheme)} aria-label={`Theme: ${theme}. Switch to ${nextTheme}`}
            className="grid size-8 place-items-center rounded-md text-ink-2 hover:bg-surface-2">
            <ThemeIcon size={16} aria-hidden />
          </button>
        </div>
      </header>

      <main className="flex-1 px-4 pb-24 pt-3">
        <Outlet />
      </main>

      <nav className="pb-safe fixed inset-x-0 bottom-0 z-20 border-t border-line bg-page/95 backdrop-blur" aria-label="Main">
        <ul className="mx-auto grid max-w-xl grid-cols-5">
          {TABS.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink to={to} end={end}
                className={({ isActive }) => `flex h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${isActive ? 'text-ink' : 'text-ink-3'}`}>
                {({ isActive }) => (
                  <>
                    <Icon size={20} strokeWidth={isActive ? 2.25 : 1.75} aria-hidden />
                    {label}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
