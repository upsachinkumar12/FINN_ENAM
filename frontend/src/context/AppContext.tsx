import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, type Health, type RefreshStatus } from '../services/api'

type Theme = 'system' | 'light' | 'dark'

interface AppState {
  health: Health | null
  refresh: RefreshStatus | null
  startRefresh: () => Promise<void>
  refreshTick: number // bumps when a refresh finishes, so pages reload their data
  theme: Theme
  setTheme: (t: Theme) => void
}

const Ctx = createContext<AppState | null>(null)

function readTheme(): Theme {
  try {
    return (localStorage.getItem('finn-theme') as Theme) || 'system'
  } catch {
    return 'system'
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null)
  const [refresh, setRefresh] = useState<RefreshStatus | null>(null)
  const [refreshTick, setTick] = useState(0)
  const [theme, setThemeState] = useState<Theme>(readTheme)

  useEffect(() => {
    const el = document.documentElement
    if (theme === 'system') el.removeAttribute('data-theme')
    else el.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('finn-theme', theme)
    } catch {
      /* private mode */
    }
  }, [theme])

  useEffect(() => {
    api.get<Health>('/api/health').then(setHealth).catch(() => setHealth(null))
    api.get<RefreshStatus>('/api/refresh/status').then(setRefresh).catch(() => undefined)
  }, [])

  // While a refresh runs, poll its status; when it finishes, tell pages to reload.
  useEffect(() => {
    if (refresh?.state !== 'running' && refresh?.state !== 'started') return
    const id = window.setInterval(async () => {
      try {
        const s = await api.get<RefreshStatus>('/api/refresh/status')
        setRefresh(s)
        if (s.state === 'done' || s.state === 'failed') setTick((t) => t + 1)
      } catch {
        /* keep polling */
      }
    }, 2500)
    return () => window.clearInterval(id)
  }, [refresh?.state])

  const startRefresh = useCallback(async () => {
    const r = await api.post<{ state: string }>('/api/market-data/refresh?days=7')
    setRefresh((prev) => ({ ...(prev ?? { started_at: null, finished_at: null }), state: r.state === 'already_running' ? 'running' : 'started' }) as RefreshStatus)
  }, [])

  return (
    <Ctx.Provider value={{ health, refresh, startRefresh, refreshTick, theme, setTheme: setThemeState }}>
      {children}
    </Ctx.Provider>
  )
}

export function useApp() {
  const c = useContext(Ctx)
  if (!c) throw new Error('useApp outside AppProvider')
  return c
}
