import { ChevronDown, SlidersHorizontal } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { AnnouncementCard } from '../components/AnnouncementCard'
import { EmptyState, ErrorState, SectionTitle, Segmented, SkeletonRows, cleanTitle } from '../components/ui'
import { useApp } from '../context/AppContext'
import { useApi } from '../hooks/useApi'
import type { Announcement, Company, Digest, Priority } from '../services/api'
import { CATEGORY_LABEL, categoryLabel, relTime } from '../utils/format'

const WINDOWS = [
  { value: '24', label: '24h' },
  { value: '72', label: '3d' },
  { value: '168', label: '7d' },
  { value: '720', label: '30d' },
]

export function FeedPage() {
  const { refreshTick } = useApp()
  const [hours, setHours] = useState('24')
  const [prio, setPrio] = useState<'all' | Priority>('all')
  const [symbol, setSymbol] = useState('')
  const [category, setCategory] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const qs = new URLSearchParams({ hours })
  if (symbol) qs.set('symbols', symbol)
  if (category) qs.set('categories', category)
  if (prio !== 'all') qs.set('priorities', prio)
  const digest = useApi<Digest>(`/api/intelligence/digest?${qs}`)
  const portfolio = useApi<{ companies: Company[] }>('/api/portfolio')

  useEffect(() => {
    if (refreshTick) void digest.reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTick])

  const activeFilters = [symbol, category, prio !== 'all' ? prio : ''].filter(Boolean).length
  const d = digest.data

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h1 className="text-xl font-bold tracking-tight">Feed</h1>
        <Segmented label="Time window" value={hours} onChange={setHours} options={WINDOWS} />
      </div>

      <button onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters}
        className="flex w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-2">
        <SlidersHorizontal size={15} aria-hidden /> Filters{activeFilters ? ` · ${activeFilters} on` : ''}
        <ChevronDown size={15} className={`ml-auto transition-transform ${showFilters ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      {showFilters && (
        <div className="mt-2 space-y-3 rounded-lg border border-line bg-surface p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-ink-3">Priority</span>
            <Segmented label="Priority" value={prio} onChange={setPrio}
              options={[{ value: 'all', label: 'All' }, { value: 'HIGH', label: 'Must' }, { value: 'MEDIUM', label: 'Worth' }, { value: 'LOW', label: 'Routine' }]} />
          </div>
          <label className="flex items-center justify-between gap-2 text-xs text-ink-3">
            Company
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}
              className="h-8 max-w-[60%] rounded-md border border-line bg-surface-2 px-2 text-sm text-ink">
              <option value="">All companies</option>
              {(portfolio.data?.companies ?? []).map((c) => <option key={c.symbol} value={c.symbol}>{c.symbol} · {c.name}</option>)}
            </select>
          </label>
          <label className="flex items-center justify-between gap-2 text-xs text-ink-3">
            Category
            <select value={category} onChange={(e) => setCategory(e.target.value)}
              className="h-8 max-w-[60%] rounded-md border border-line bg-surface-2 px-2 text-sm text-ink">
              <option value="">All categories</option>
              {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          {activeFilters > 0 && (
            <button onClick={() => { setSymbol(''); setCategory(''); setPrio('all') }} className="text-xs text-ink-2 underline underline-offset-2">
              Clear filters
            </button>
          )}
        </div>
      )}

      {digest.error && !d ? (
        <div className="mt-4"><ErrorState message={digest.error} onRetry={digest.reload} /></div>
      ) : !d ? (
        <div className="mt-4"><SkeletonRows n={5} h={88} /></div>
      ) : (
        <div className={digest.loading ? 'opacity-60 transition-opacity' : ''}>
          <p className="mt-3 text-xs text-ink-3">
            {d.counts.filings} filings · {d.counts.events} events · exchange feed checked {relTime(d.freshness.last_success)}
            {d.freshness.failures.length > 0 && ` · ${d.freshness.failures.length} source error${d.freshness.failures.length > 1 ? 's' : ''}`}
          </p>
          {d.counts.filings === 0 && (
            <div className="mt-4"><EmptyState title="No filings in this window">Try a longer window, or clear the filters.</EmptyState></div>
          )}
          <Band title="Must read" items={d.must_read} />
          <Band title="Worth a look" items={d.worth_a_look} compact />
          <Buried items={d.buried} />
        </div>
      )}
    </div>
  )
}

function Band({ title, items, compact }: { title: string; items: Announcement[]; compact?: boolean }) {
  if (!items.length) return null
  return (
    <>
      <SectionTitle aside={<span className="text-xs text-ink-3">{items.length}</span>}>{title}</SectionTitle>
      <div className="space-y-2.5">{items.map((a) => <AnnouncementCard key={a.id} a={a} compact={compact} />)}</div>
    </>
  )
}

/** Routine filings stay one tap away, summarised by why they were buried. */
function Buried({ items }: { items: Announcement[] }) {
  const [open, setOpen] = useState(false)
  const byCat = useMemo(() => {
    const m = new Map<string, number>()
    for (const a of items) m.set(a.category, (m.get(a.category) ?? 0) + 1 + (a.related?.length ?? 0))
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }, [items])
  if (!items.length) return null
  return (
    <div className="mt-6 rounded-xl border border-line bg-surface">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex w-full items-start gap-2 px-4 py-3 text-left">
        <div className="flex-1">
          <p className="eyebrow">Buried · {items.length}</p>
          <p className="mt-1 text-sm text-ink-2">{byCat.slice(0, 4).map(([c, n]) => `${n} ${categoryLabel(c).toLowerCase()}`).join(', ')}{byCat.length > 4 ? ', …' : ''}</p>
        </div>
        <ChevronDown size={16} className={`mt-1 text-ink-3 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>
      {open && (
        <ul className="divide-y divide-line border-t border-line">
          {items.map((a) => (
            <li key={a.id} className="px-4 py-2.5 text-sm">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-semibold">{a.symbol}</span>
                <a href={a.pdf_url ?? a.filing_page_url ?? '#'} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-ink-2 hover:text-ink">
                  {cleanTitle(a.title)}
                </a>
                <span className="shrink-0 text-[11px] text-ink-3">{relTime(a.published_at)}</span>
              </div>
              <p className="mt-0.5 text-[11px] text-ink-3">{a.priority_reason}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
