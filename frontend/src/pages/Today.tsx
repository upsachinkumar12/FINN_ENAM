import { Activity, Check, ChevronRight, ExternalLink, Volume2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AnnouncementCard } from '../components/AnnouncementCard'
import { Delta, EmptyState, ErrorState, Segmented, SectionTitle, SkeletonRows, Spark, Term, cleanTitle } from '../components/ui'
import { useApp } from '../context/AppContext'
import { useApi } from '../hooks/useApi'
import type { Alert, Announcement, Company, Digest } from '../services/api'
import { compactVolume, multiple, price } from '../utils/format'

type Win = '24' | '72' | '168'
const WIN_LABEL: Record<Win, string> = { '24': 'last 24 hours', '72': 'last 3 days', '168': 'last 7 days' }

function useCleared() {
  const [ids, setIds] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem('finn-cleared') ?? '[]'))
    } catch {
      return new Set()
    }
  })
  const clear = (id: string) =>
    setIds((prev) => {
      const next = new Set(prev).add(id)
      try {
        localStorage.setItem('finn-cleared', JSON.stringify([...next].slice(-500)))
      } catch {
        /* storage unavailable: clearing still works for this session */
      }
      return next
    })
  return { cleared: ids, clear }
}

export function TodayPage() {
  const { refreshTick } = useApp()
  const [win, setWin] = useState<Win>('24')
  const digest = useApi<Digest>(`/api/intelligence/digest?hours=${win}`)
  const portfolio = useApi<{ companies: Company[] }>('/api/portfolio')
  const alerts = useApi<{ alerts: Alert[] }>('/api/alerts?limit=300')
  // Filings near a price move are matched over a week, independent of the brief's window.
  const recentFilings = useApi<{ items: Announcement[] }>('/api/announcements?hours=168&priorities=HIGH,MEDIUM')
  const { cleared, clear } = useCleared()

  useEffect(() => {
    if (refreshTick) {
      void digest.reload()
      void portfolio.reload()
      void alerts.reload()
      void recentFilings.reload()
    }
    // reload only when a refresh completes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTick])

  const lastSession = useMemo(() => {
    const dates = (portfolio.data?.companies ?? []).map((c) => c.market?.date).filter(Boolean) as string[]
    return dates.sort().at(-1) ?? null
  }, [portfolio.data])

  const moves = useMemo(
    () => (alerts.data?.alerts ?? []).filter((a) => a.kind !== 'announcement' && a.trade_date === lastSession),
    [alerts.data, lastSession],
  )

  const d = digest.data
  const mustRead = (d?.must_read ?? []).filter((a) => !cleared.has(a.id))
  const moveKeys = moves.map((m) => `move:${m.id}`).filter((k) => !cleared.has(k))
  const done = d && mustRead.length === 0 && moveKeys.length === 0

  return (
    <div>
      <Heading lastSession={lastSession} />

      {digest.error && !d ? (
        <ErrorState message={digest.error} onRetry={digest.reload} />
      ) : !d ? (
        <SkeletonRows n={3} h={92} />
      ) : (
        <>
          <Funnel d={d} win={win} setWin={setWin} />

          {done ? (
            <DoneState d={d} win={win} onWiden={win !== '168' ? () => setWin(win === '24' ? '72' : '168') : undefined} />
          ) : (
            <>
              {mustRead.length > 0 && (
                <>
                  <SectionTitle aside={<span className="text-xs text-ink-3">{mustRead.length} left</span>}>Must read</SectionTitle>
                  <div className="space-y-3">
                    {mustRead.map((a) => (
                      <Clearable key={a.id} onClear={() => clear(a.id)}>
                        <AnnouncementCard a={a} />
                      </Clearable>
                    ))}
                  </div>
                </>
              )}
              {moveKeys.length > 0 && (
                <>
                  <SectionTitle aside={<span className="text-xs text-ink-3"><Term k="EOD">EOD</Term> {lastSession}</span>}>Unusual moves</SectionTitle>
                  <div className="space-y-2">
                    {groupMoves(moves).filter((g) => !cleared.has(`move:${g[0].id}`)).map((g) => (
                      <Clearable key={g[0].id} onClear={() => g.forEach((m) => clear(`move:${m.id}`))}>
                        <MoveCard group={g} filings={recentFilings.data?.items ?? []} />
                      </Clearable>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {d.worth_a_look.length > 0 && (
            <Link to="/feed" className="mt-4 flex items-center justify-between rounded-xl border border-line bg-surface px-4 py-3 text-sm">
              <span><span className="font-semibold">{d.worth_a_look.length}</span> worth a look, <span className="font-semibold">{d.buried.length}</span> routine buried</span>
              <ChevronRight size={16} className="text-ink-3" aria-hidden />
            </Link>
          )}
        </>
      )}

      <SectionTitle aside={<Link to="/alerts" className="text-xs text-ink-3 underline underline-offset-2">Alert rules</Link>}>Portfolio</SectionTitle>
      {portfolio.error && !portfolio.data ? (
        <ErrorState message={portfolio.error} onRetry={portfolio.reload} />
      ) : !portfolio.data ? (
        <SkeletonRows n={6} h={52} />
      ) : (
        <PortfolioList companies={portfolio.data.companies} alertSymbols={new Set(moves.map((m) => m.symbol))} />
      )}
    </div>
  )
}

function Heading({ lastSession }: { lastSession: string | null }) {
  const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })
  return (
    <div className="mb-3">
      <h1 className="text-xl font-bold tracking-tight">{today}</h1>
      <p className="text-xs text-ink-3">
        {lastSession ? <>Prices: close of {new Date(lastSession).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })} (end of day, not live)</> : 'No price data yet'}
      </p>
    </div>
  )
}

function Funnel({ d, win, setWin }: { d: Digest; win: Win; setWin: (w: Win) => void }) {
  const c = d.counts
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="eyebrow">Filings, {WIN_LABEL[win]}</p>
        <Segmented label="Time window" value={win} onChange={setWin}
          options={[{ value: '24', label: '24h' }, { value: '72', label: '3d' }, { value: '168', label: '7d' }]} />
      </div>
      <div className="mt-3 flex items-end gap-2 text-sm">
        <Stage n={c.filings} label="filed" />
        <Arrow />
        <Stage n={c.high + c.medium} label="worth a look" />
        <Arrow />
        <Stage n={c.high} label="must read" strong />
      </div>
      {c.filings > c.events && (
        <p className="mt-2 text-xs text-ink-3">{c.filings - c.events} duplicate filings folded into the events they belong to.</p>
      )}
    </div>
  )
}

function Stage({ n, label, strong }: { n: number; label: string; strong?: boolean }) {
  return (
    <div className="min-w-0">
      <div className={`text-2xl font-bold leading-none ${strong && n > 0 ? 'text-accent' : ''}`}>{n}</div>
      <div className="mt-1 text-[11px] text-ink-3">{label}</div>
    </div>
  )
}

const Arrow = () => <span className="mb-4 flex-1 border-t border-dashed border-line-strong" aria-hidden />

function Clearable({ children, onClear }: { children: React.ReactNode; onClear: () => void }) {
  return (
    <div>
      {children}
      <div className="mt-1 flex justify-end">
        <button onClick={onClear} aria-label="Mark as read"
          className="inline-flex h-8 items-center gap-1 rounded-full px-3 text-xs font-medium text-ink-3 hover:bg-surface-2 hover:text-ink">
          <Check size={13} aria-hidden /> Got it
        </button>
      </div>
    </div>
  )
}

function DoneState({ d, win, onWiden }: { d: Digest; win: Win; onWiden?: () => void }) {
  const nothing = d.counts.high === 0
  return (
    <div className="mt-3 rounded-xl border border-line bg-surface p-5 text-center">
      <Check className="mx-auto text-up" size={22} aria-hidden />
      <p className="mt-2 font-semibold">{nothing ? `Nothing material in the ${WIN_LABEL[win]}` : 'You’re through today’s brief'}</p>
      <p className="mt-1 text-sm text-ink-2">
        FINN read the exchange feed for your {d.counts.filings ? `${d.counts.filings} filings` : 'portfolio'} and buried {d.buried.length} routine items.
      </p>
      {onWiden && nothing && (
        <button onClick={onWiden} className="mt-3 rounded-lg bg-surface-2 px-3 py-1.5 text-sm font-medium">Look further back</button>
      )}
    </div>
  )
}

function groupMoves(moves: Alert[]): Alert[][] {
  const by = new Map<string, Alert[]>()
  for (const m of moves) by.set(m.symbol, [...(by.get(m.symbol) ?? []), m])
  return [...by.values()].sort((a, b) => Math.abs(b[0].details.return_pct ?? 0) - Math.abs(a[0].details.return_pct ?? 0))
}

function MoveCard({ group, filings }: { group: Alert[]; filings: Announcement[] }) {
  const a = group[0]
  const det = a.details
  const rules = new Set(group.map((g) => g.kind))
  const day = new Date(a.trade_date).getTime()
  const nearby = filings.filter((f) => f.symbol === a.symbol && Math.abs(new Date(f.published_at).getTime() - day) < 3 * 86400000)
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3">
      <div className="flex items-center gap-2 text-xs text-ink-3">
        {rules.has('volume') ? <Volume2 size={13} aria-hidden /> : <Activity size={13} aria-hidden />}
        <span className="font-semibold text-ink">{a.symbol}</span>
        <span className="truncate">{a.name}</span>
      </div>
      <div className="mt-1.5 flex items-baseline gap-3">
        <Delta value={det.return_pct ?? null} className="text-lg font-bold" />
        <span className="num text-sm text-ink-2">{price(det.close)}</span>
        {det.volume_multiple != null && (
          <span className={`num ml-auto text-sm ${rules.has('volume') ? 'font-semibold text-ink' : 'text-ink-3'}`}>
            {multiple(det.volume_multiple)} <span className="font-normal text-ink-3">avg vol</span>
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-ink-3">
        Volume {compactVolume(det.volume)} vs {compactVolume(det.avg_volume)} 20-session average. {group.map((g) => g.details.reason.split(',')[0]).join('; ')}.
      </p>
      {nearby.length > 0 ? (
        <div className="mt-2 rounded-lg bg-surface-2 px-3 py-2 text-xs">
          <p className="text-ink-3">Possibly related — filed around the same time (FINN can’t establish cause):</p>
          <ul className="mt-1 space-y-0.5">
            {nearby.slice(0, 3).map((f) => <li key={f.id} className="truncate font-medium">{f.summary?.what_happened ?? cleanTitle(f.title)}</li>)}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-xs text-ink-3">No filing from {a.symbol} around this move.</p>
      )}
      <a href={det.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs text-ink-2 underline underline-offset-2">
        Price history <ExternalLink size={11} aria-hidden />
      </a>
    </div>
  )
}

function PortfolioList({ companies, alertSymbols }: { companies: Company[]; alertSymbols: Set<string> }) {
  if (!companies.length) return <EmptyState title="Your portfolio is empty">Add companies from Research.</EmptyState>
  const sorted = [...companies].sort((a, b) => Math.abs(b.market?.return_pct ?? 0) - Math.abs(a.market?.return_pct ?? 0))
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
      {sorted.map((c) => (
        <li key={c.symbol}>
          <Link to={`/research/${c.symbol}`} className="flex items-center gap-3 px-4 py-2.5">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold">{c.symbol}</span>
                {alertSymbols.has(c.symbol) && <span className="size-1.5 rounded-full bg-accent-fill" aria-label="Unusual move" />}
                {c.high_priority_7d > 0 && <span className="whitespace-nowrap text-[10px] font-semibold text-accent">{c.high_priority_7d} must-read</span>}
              </div>
              <div className="truncate text-xs text-ink-3">{c.name}</div>
            </div>
            <Spark values={c.market?.spark ?? []} />
            <div className="w-20 text-right">
              <div className="num text-sm">{price(c.market?.close)}</div>
              <div className="text-xs"><Delta value={c.market?.return_pct ?? null} /></div>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  )
}
