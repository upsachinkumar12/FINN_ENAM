import { Activity, Check, ExternalLink, FileText, Minus, Plus, Volume2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Delta, EmptyState, ErrorState, SectionTitle, SkeletonRows, Term } from '../components/ui'
import { useApp } from '../context/AppContext'
import { useApi } from '../hooks/useApi'
import { api, type Alert, type AlertSettings, type Company, type Priority } from '../services/api'
import { CATEGORY_LABEL, compactVolume, dateLabel, multiple, price } from '../utils/format'

export function AlertsPage() {
  const { refreshTick } = useApp()
  const data = useApi<{ alerts: Alert[]; settings: AlertSettings }>('/api/alerts?limit=300')
  const portfolio = useApi<{ companies: Company[] }>('/api/portfolio')
  const [filter, setFilter] = useState<'all' | 'market' | 'filings'>('all')

  useEffect(() => {
    if (refreshTick) void data.reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTick])

  const list = useMemo(() => (data.data?.alerts ?? []).filter((a) =>
    filter === 'all' ? true : filter === 'market' ? a.kind !== 'announcement' : a.kind === 'announcement'), [data.data, filter])
  const byDate = useMemo(() => {
    const m = new Map<string, Alert[]>()
    for (const a of list) m.set(a.trade_date, [...(m.get(a.trade_date) ?? []), a])
    return [...m.entries()]
  }, [list])

  return (
    <div>
      <h1 className="mb-1 text-xl font-bold tracking-tight">Alerts</h1>
      <p className="mb-3 text-xs text-ink-3">You decide what “unusual” means. FINN checks every <Term k="EOD">end-of-day</Term> close against it — these are not intraday alerts.</p>

      {data.error && !data.data ? <ErrorState message={data.error} onRetry={data.reload} />
        : !data.data ? <SkeletonRows n={3} h={120} />
        : <SettingsPanel initial={data.data.settings} companies={portfolio.data?.companies ?? []} onSaved={data.reload} />}

      <SectionTitle aside={
        <div className="flex gap-1 text-xs">
          {(['all', 'market', 'filings'] as const).map((f) => (
            <button key={f} onClick={() => setFilter(f)} className={`rounded px-2 py-0.5 ${filter === f ? 'bg-surface-2 font-semibold text-ink' : 'text-ink-3'}`}>{f}</button>
          ))}
        </div>
      }>History</SectionTitle>
      {data.data && list.length === 0 && <EmptyState title="Nothing has crossed your thresholds">Loosen a threshold above, or wait for the next close.</EmptyState>}
      <div className="space-y-5">
        {byDate.map(([date, items]) => (
          <section key={date}>
            <h3 className="mb-1.5 text-xs font-semibold text-ink-2">{dateLabel(date)}</h3>
            <div className="space-y-2">{items.map((a) => <AlertRow key={a.id} a={a} />)}</div>
          </section>
        ))}
      </div>
    </div>
  )
}

function Stepper({ label, term, value, onChange, step, min, max, format }: {
  label: string; term?: string; value: number; onChange: (v: number) => void; step: number; min: number; max: number; format: (v: number) => string
}) {
  const set = (v: number) => onChange(Math.min(max, Math.max(min, Math.round(v * 100) / 100)))
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm">{term ? <Term k={term}>{label}</Term> : label}</span>
      <div className="flex items-center rounded-lg border border-line">
        <button onClick={() => set(value - step)} aria-label={`Decrease ${label}`} className="grid size-9 place-items-center text-ink-2"><Minus size={14} /></button>
        <span className="num w-16 text-center text-sm font-semibold" aria-live="polite">{format(value)}</span>
        <button onClick={() => set(value + step)} aria-label={`Increase ${label}`} className="grid size-9 place-items-center text-ink-2"><Plus size={14} /></button>
      </div>
    </div>
  )
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={`relative h-6 w-10 shrink-0 rounded-full transition-colors ${on ? 'bg-ink' : 'bg-line-strong'}`}>
      <span className={`absolute left-0 top-0.5 size-5 rounded-full bg-page transition-transform ${on ? 'translate-x-[18px]' : 'translate-x-0.5'}`} />
    </button>
  )
}

function SettingsPanel({ initial, companies, onSaved }: { initial: AlertSettings; companies: Company[]; onSaved: () => void }) {
  const [s, setS] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const dirty = JSON.stringify(s) !== JSON.stringify(initial)
  const en = s.enabled
  const setEn = (k: keyof AlertSettings['enabled'], v: boolean) => setS({ ...s, enabled: { ...en, [k]: v } })
  const monitored = new Set(s.symbols ?? companies.map((c) => c.symbol))

  const toggleSymbol = (sym: string) => {
    const next = new Set(monitored)
    if (next.has(sym)) next.delete(sym)
    else next.add(sym)
    setS({ ...s, symbols: next.size === companies.length ? null : [...next] })
  }
  const toggleCat = (c: string) =>
    setS({ ...s, announcement_categories: s.announcement_categories.includes(c) ? s.announcement_categories.filter((x) => x !== c) : [...s.announcement_categories, c] })

  async function save() {
    setSaving(true)
    setMsg(null)
    try {
      const r = await api.post<{ scan: { new_alerts: number } }>('/api/alerts/settings', s)
      setMsg(r.scan.new_alerts ? `Saved. ${r.scan.new_alerts} new alert${r.scan.new_alerts > 1 ? 's' : ''} under the new rules.` : 'Saved. No new alerts under these rules.')
      onSaved()
    } catch (e) {
      setMsg((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="divide-y divide-line rounded-xl border border-line bg-surface">
      <div className="space-y-3 p-4">
        <p className="eyebrow">Price & volume</p>
        <div className="flex items-center gap-3"><Toggle on={en.price_up} onChange={(v) => setEn('price_up', v)} label="Price up alerts" />
          <div className="flex-1"><Stepper label="Rises at least" value={s.price_up_pct} onChange={(v) => setS({ ...s, price_up_pct: v })} step={0.5} min={0.5} max={50} format={(v) => `+${v}%`} /></div></div>
        <div className="flex items-center gap-3"><Toggle on={en.price_down} onChange={(v) => setEn('price_down', v)} label="Price down alerts" />
          <div className="flex-1"><Stepper label="Falls at least" value={s.price_down_pct} onChange={(v) => setS({ ...s, price_down_pct: v })} step={0.5} min={0.5} max={50} format={(v) => `−${v}%`} /></div></div>
        <div className="flex items-center gap-3"><Toggle on={en.volume} onChange={(v) => setEn('volume', v)} label="Volume alerts" />
          <div className="flex-1"><Stepper label="Volume vs 20-day avg" value={s.volume_multiple} onChange={(v) => setS({ ...s, volume_multiple: v })} step={0.25} min={1.25} max={20} format={(v) => `${v}×`} /></div></div>
      </div>

      <div className="space-y-3 p-4">
        <div className="flex items-center gap-3">
          <Toggle on={en.announcement} onChange={(v) => setEn('announcement', v)} label="Filing alerts" />
          <span className="flex-1 text-sm">Alert on <Term k="Material announcement">material filings</Term></span>
          <select value={s.announcement_min_priority} onChange={(e) => setS({ ...s, announcement_min_priority: e.target.value as Priority })}
            className="h-8 rounded-md border border-line bg-surface-2 px-2 text-xs" aria-label="Minimum priority">
            <option value="HIGH">Must-read only</option>
            <option value="MEDIUM">Worth a look +</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(CATEGORY_LABEL).filter(([k]) => k !== 'unclassified').map(([k, v]) => {
            const on = s.announcement_categories.includes(k)
            return (
              <button key={k} onClick={() => toggleCat(k)} aria-pressed={on}
                className={`h-7 rounded-full border px-2.5 text-xs ${on ? 'border-ink bg-ink text-page' : 'border-line text-ink-2'}`}>{v}</button>
            )
          })}
        </div>
      </div>

      <details className="group p-4">
        <summary className="flex cursor-pointer list-none items-center justify-between text-sm">
          <span>Watching <span className="font-semibold">{monitored.size}</span> of {companies.length} companies</span>
          <span className="text-xs text-ink-3 group-open:hidden">Choose</span>
        </summary>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {companies.map((c) => {
            const on = monitored.has(c.symbol)
            return (
              <button key={c.symbol} onClick={() => toggleSymbol(c.symbol)} aria-pressed={on}
                className={`h-7 rounded-full border px-2.5 text-xs ${on ? 'border-ink-2 text-ink' : 'border-line text-ink-3 line-through'}`}>{c.symbol}</button>
            )
          })}
        </div>
      </details>

      <div className="flex items-center gap-3 p-4">
        <button onClick={save} disabled={!dirty || saving}
          className="h-9 rounded-lg bg-ink px-4 text-sm font-semibold text-page disabled:opacity-40">{saving ? 'Saving…' : 'Save & re-check'}</button>
        {dirty && <button onClick={() => { setS(initial); setMsg(null) }} className="text-sm text-ink-2">Undo</button>}
        {msg && <p className="flex items-center gap-1 text-xs text-ink-2" role="status"><Check size={13} aria-hidden /> {msg}</p>}
      </div>
    </div>
  )
}

function AlertRow({ a }: { a: Alert }) {
  const d = a.details
  const Icon = a.kind === 'announcement' ? FileText : a.kind === 'volume' ? Volume2 : Activity
  const [read, setRead] = useState(!!a.acknowledged)
  return (
    <div className={`rounded-xl border border-line bg-surface px-4 py-3 ${read ? 'opacity-70' : ''}`}>
      <div className="flex items-center gap-2 text-xs">
        <Icon size={13} className="text-ink-3" aria-hidden />
        <span className="font-semibold">{a.symbol}</span>
        <span className="truncate text-ink-3">{a.name}</span>
        {a.kind === 'volume' && <span className="num ml-auto font-semibold">{multiple(a.value)}</span>}
        {(a.kind === 'price_up' || a.kind === 'price_down') && <Delta value={a.value} className="ml-auto font-semibold" />}
      </div>
      <p className="mt-1 text-sm">{d.reason}</p>
      {a.kind !== 'announcement' && (
        <dl className="num mt-2 grid grid-cols-3 gap-2 text-[11px]">
          <div><dt className="text-ink-3">Close</dt><dd>{price(d.close)}</dd></div>
          <div><dt className="text-ink-3">Volume</dt><dd>{compactVolume(d.volume)}</dd></div>
          <div><dt className="text-ink-3">20-day avg</dt><dd>{compactVolume(d.avg_volume)}</dd></div>
        </dl>
      )}
      <div className="mt-2 flex items-center gap-3 text-xs">
        {d.source_url && (
          <a href={d.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink-2 underline underline-offset-2">
            {a.kind === 'announcement' ? 'Filing' : 'Market data'} <ExternalLink size={11} aria-hidden />
          </a>
        )}
        {a.threshold != null && <span className="text-ink-3">Rule: {a.kind === 'volume' ? `${a.threshold}×` : `${a.threshold > 0 ? '+' : ''}${a.threshold}%`}</span>}
        {!read && (
          <button onClick={async () => { await api.post(`/api/alerts/${a.id}/ack`); setRead(true) }}
            className="ml-auto text-ink-3 hover:text-ink">Mark seen</button>
        )}
      </div>
    </div>
  )
}
