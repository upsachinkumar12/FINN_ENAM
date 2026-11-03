import {
  ArrowUpRight, Check, CircleHelp, Clock, ExternalLink, FileUp, Link2, Loader2, MessageCircle, Plus, Search, X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { BarSeries, PctLine } from '../components/Charts'
import { CitedText, SourceSheet } from '../components/Cited'
import { Delta, EmptyState, ErrorState, SectionTitle, SkeletonRows, Term } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { api, type CompanyResearch, type Financials, type LabelledPoint, type Promise_, type ResearchJob } from '../services/api'
import { amt, price, relTime } from '../utils/format'

export function ResearchPage() {
  const { symbol } = useParams()
  return symbol ? <CompanyView symbol={symbol.toUpperCase()} key={symbol} /> : <SearchView />
}

// ---------------- search ----------------

function SearchView() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(q.trim()), 250)
    return () => window.clearTimeout(t)
  }, [q])
  const results = useApi<{ results: { symbol: string; name: string; known: boolean; in_portfolio?: number }[] }>(
    debounced ? `/api/companies/search?q=${encodeURIComponent(debounced)}` : null)
  const portfolio = useApi<{ companies: { symbol: string; name: string }[] }>('/api/portfolio')
  const navigate = useNavigate()

  return (
    <div>
      <h1 className="mb-1 text-xl font-bold tracking-tight">Research</h1>
      <p className="mb-3 text-xs text-ink-3">Any NSE company. FINN reads its annual report and earnings calls — primary sources only, no news or broker views.</p>
      <form onSubmit={(e) => { e.preventDefault(); if (q.trim()) navigate(`/research/${q.trim().toUpperCase()}`) }} className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Company name or NSE symbol" autoFocus
          aria-label="Search companies" className="h-11 w-full rounded-xl border border-line bg-surface pl-9 pr-3 text-[15px] outline-none focus:border-ink-3" />
      </form>
      {debounced && (
        <ul className="mt-2 divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
          {results.loading && !results.data && <li className="px-4 py-3 text-sm text-ink-3">Searching…</li>}
          {results.data?.results.length === 0 && <li className="px-4 py-3 text-sm text-ink-3">No listed company matches “{debounced}”. Try the exact NSE symbol.</li>}
          {results.data?.results.map((r) => (
            <li key={r.symbol}>
              <Link to={`/research/${r.symbol}`} className="flex items-center gap-3 px-4 py-2.5">
                <span className="text-sm font-semibold">{r.symbol}</span>
                <span className="truncate text-sm text-ink-2">{r.name}</span>
                {r.in_portfolio ? <span className="ml-auto text-[11px] text-ink-3">in portfolio</span> : null}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <SectionTitle>Research picks</SectionTitle>
      <div className="flex flex-wrap gap-1.5">
        {['HAL', 'BEL', 'ASIANPAINT', 'COALINDIA', 'POWERGRID'].map((s) => (
          <Link key={s} to={`/research/${s}`} className="h-8 rounded-full border border-line px-3 text-sm leading-8">{s}</Link>
        ))}
      </div>
      <SectionTitle>Your portfolio</SectionTitle>
      <div className="flex flex-wrap gap-1.5">
        {(portfolio.data?.companies ?? []).map((c) => (
          <Link key={c.symbol} to={`/research/${c.symbol}`} className="h-8 rounded-full bg-surface-2 px-3 text-sm leading-8 text-ink-2">{c.symbol}</Link>
        ))}
      </div>
    </div>
  )
}

// ---------------- company ----------------

const SECTIONS = [['snapshot', 'Snapshot'], ['trajectory', 'Trajectory'], ['ledger', 'Promises'], ['case', 'Bull / bear'],
  ['balance', 'Balance sheet'], ['cash', 'Cash'], ['sources', 'Sources']] as const

function CompanyView({ symbol }: { symbol: string }) {
  const r = useApi<CompanyResearch>(`/api/company/${symbol}`)
  const [job, setJob] = useState<ResearchJob | null>(null)

  useEffect(() => { if (r.data?.job) setJob(r.data.job) }, [r.data?.job])
  useEffect(() => {
    if (job?.status !== 'running') return
    const id = window.setInterval(async () => {
      const j = await api.get<ResearchJob>(`/api/research/jobs/${job.id}`).catch(() => null)
      if (!j) return
      setJob(j)
      if (j.status !== 'running') void r.reload()
    }, 2000)
    return () => window.clearInterval(id)
  }, [job?.id, job?.status, r])

  async function startJob() {
    setJob(await api.post<ResearchJob>(`/api/research/${symbol}/generate`))
  }

  if (r.error && !r.data) return <><BackLink /><ErrorState message={r.error} onRetry={r.reload} /></>
  if (!r.data) return <><BackLink /><SkeletonRows n={4} h={120} /></>
  const fin = r.data.sections.financials?.data
  if (!fin) return <><BackLink /><EmptyState title="No reported financials found">{symbol} may not be covered yet.</EmptyState></>
  const s = r.data.sections
  const hasDocs = r.data.documents.some((d) => d.status === 'ready')

  return (
    <div>
      <BackLink />
      <Header fin={fin} company={r.data.company} onChanged={r.reload} />
      <nav className="sticky top-12 z-10 -mx-4 mb-1 flex gap-1 overflow-x-auto border-b border-line bg-page/95 px-4 py-2 backdrop-blur [scrollbar-width:none]" aria-label="Sections">
        {SECTIONS.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="h-7 shrink-0 rounded-full bg-surface-2 px-3 text-xs font-medium leading-7 text-ink-2">{label}</a>
        ))}
      </nav>

      {(!s.ledger || job?.status === 'running') && (
        <ReadDocsCard job={job} onStart={startJob} llm={r.data.llm_configured} hasDocs={hasDocs} />
      )}

      {s.business && (
        <section className="mt-4">
          <SectionTitle>What the business does</SectionTitle>
          <CitedText segments={s.business.data.segments} className="text-sm text-ink-2" />
        </section>
      )}

      <Snapshot fin={fin} />
      <Trajectory fin={fin} />
      <Ledger data={s.ledger?.data} conclusion={s.bull_bear?.data.ledger_conclusion ?? null} />
      <BullBear data={s.bull_bear?.data} />
      <Balance fin={fin} />
      <Cash fin={fin} />
      <Sources symbol={symbol} docs={r.data.documents} fin={fin} onAdded={r.reload} />
      <Link to={`/ask?symbol=${symbol}`} className="mt-6 flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-sm">
        <MessageCircle size={16} className="text-ink-3" aria-hidden /> Ask FINN about {fin.name}
        <ArrowUpRight size={15} className="ml-auto text-ink-3" aria-hidden />
      </Link>
    </div>
  )
}

const BackLink = () => <Link to="/research" className="mb-2 inline-block text-xs text-ink-3">← All companies</Link>

function Header({ fin, company, onChanged }: { fin: Financials; company: CompanyResearch['company']; onChanged: () => void }) {
  const market = useApi<{ latest: { close: number; return_pct: number | null; date: string } | null }>(`/api/market-data/${fin.symbol}?sessions=30`)
  const [busy, setBusy] = useState(false)
  const inPf = !!company?.in_portfolio
  async function toggle() {
    setBusy(true)
    try {
      if (inPf) await api.del(`/api/portfolio/${fin.symbol}`)
      else await api.post('/api/portfolio', { symbol: fin.symbol, in_portfolio: true })
      onChanged()
    } finally {
      setBusy(false)
    }
  }
  const l = market.data?.latest
  const kr = fin.key_ratios
  return (
    <header>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold leading-tight tracking-tight">{fin.name}</h1>
          <p className="text-xs text-ink-3">{fin.symbol} · {company?.sector ?? 'NSE'} · {fin.basis} figures</p>
        </div>
        <button onClick={toggle} disabled={busy} className="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg border border-line px-2.5 text-xs font-medium">
          {inPf ? <><Check size={13} aria-hidden /> In portfolio</> : <><Plus size={13} aria-hidden /> Add to portfolio</>}
        </button>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="num text-2xl font-bold">{l ? price(l.close) : '—'}</span>
        {l && <Delta value={l.return_pct} className="text-sm font-semibold" />}
        {l && <span className="text-[11px] text-ink-3">close {l.date}</span>}
      </div>
      <dl className="mt-2 grid grid-cols-4 gap-2 text-[11px]">
        {([['Market Cap', 'Market cap'], ['Stock P/E', 'P/E'], ['ROCE', 'ROCE'], ['ROE', 'ROE']] as const).map(([k, label]) => (
          <div key={k} className="rounded-lg bg-surface-2 px-2 py-1.5">
            <dt className="text-ink-3">{label === 'P/E' ? label : <Term k={label === 'Market cap' ? 'Market cap' : label}>{label}</Term>}</dt>
            <dd className="num mt-0.5 truncate font-semibold">{kr[k]?.replace('₹', '').replace('Cr.', 'cr') ?? '—'}</dd>
          </div>
        ))}
      </dl>
    </header>
  )
}

function ReadDocsCard({ job, onStart, llm, hasDocs }: { job: ResearchJob | null; onStart: () => void; llm: boolean; hasDocs: boolean }) {
  const running = job?.status === 'running'
  return (
    <div className="mt-4 rounded-xl border border-line bg-surface p-4">
      {!job || (!running && job.status !== 'done') ? (
        <>
          <p className="text-sm font-semibold">Read the annual report and the last four earnings calls</p>
          <p className="mt-1 text-xs text-ink-2">
            Builds the Promise Ledger and a cited bull/bear case. Takes 1–3 minutes the first time; cached after.
            {!llm && ' The AI steps are off on this server (no API key), so FINN will index the documents only.'}
          </p>
          {job?.status === 'failed' && <p className="mt-2 text-xs text-down">Last attempt failed: {job.error?.split('\n')[0]}</p>}
          <button onClick={onStart} className="mt-3 h-9 rounded-lg bg-ink px-4 text-sm font-semibold text-page">
            {hasDocs ? 'Re-run analysis' : 'Start reading'}
          </button>
        </>
      ) : (
        <>
          <p className="text-sm font-semibold">{running ? 'Reading primary documents…' : 'Analysis finished'}</p>
          <ol className="mt-2 space-y-1.5">
            {job.steps.map((s) => (
              <li key={s.name} className="flex items-start gap-2 text-xs">
                <span className="mt-0.5 shrink-0">
                  {s.state === 'running' ? <Loader2 size={13} className="animate-spin text-accent" aria-hidden />
                    : s.state === 'done' ? <Check size={13} className="text-up" aria-hidden />
                    : s.state === 'failed' ? <X size={13} className="text-down" aria-hidden />
                    : <span className="block size-[13px] rounded-full border border-line-strong" aria-hidden />}
                </span>
                <span className={s.state === 'pending' ? 'text-ink-3' : ''}>
                  {s.name}{s.detail && <span className="text-ink-3"> — {s.detail}</span>}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}

function Snapshot({ fin }: { fin: Financials }) {
  const sn = fin.snapshot
  return (
    <section id="snapshot" className="scroll-mt-28">
      <SectionTitle aside={<span className="text-xs text-ink-3">{sn.period_label} · ₹ crore</span>}>Financial snapshot</SectionTitle>
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="num w-full whitespace-nowrap text-sm">
          <thead className="bg-surface-2 text-[11px] text-ink-3">
            <tr>
              <th className="px-3 py-2 text-left font-medium" />
              <th className="px-2 py-2 text-right font-medium">{sn.period ?? 'Latest'}</th>
              <th className="px-2 py-2 text-right font-medium"><Term k="QoQ" /></th>
              <th className="px-3 py-2 text-right font-medium"><Term k="YoY" /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {sn.rows.map((r) => {
              const isPct = r.metric.endsWith('%')
              return (
                <tr key={r.metric}>
                  <td className="whitespace-normal px-3 py-2.5 font-medium">
                    <Term k={r.metric.replace(' %', '')}>{r.metric}</Term>
                    {r.note && <div className="text-[10px] font-normal leading-tight text-ink-3">{r.note}</div>}
                  </td>
                  <td className="px-2 py-2.5 text-right">{isPct ? (r.current == null ? '—' : `${r.current.toFixed(2)}%`) : amt(r.current)}</td>
                  <td className="px-2 py-2.5 text-right">{isPct ? <PpDelta a={r.current} b={r.prev_q} /> : <Delta value={r.qoq} digits={1} />}</td>
                  <td className="px-3 py-2.5 text-right">{isPct ? <PpDelta a={r.current} b={r.year_ago} /> : <Delta value={r.yoy} digits={1} />}</td>
                </tr>
              )
            })}
            {sn.margin && (
              <tr>
                <td className="px-3 py-2.5 font-medium"><Term k="Margin">{sn.margin.label}</Term></td>
                <td className="px-2 py-2.5 text-right">{sn.margin.current == null ? '—' : `${sn.margin.current}%`}</td>
                <td className="px-2 py-2.5 text-right"><PpDelta a={sn.margin.current} b={sn.margin.prev_q} /></td>
                <td className="px-3 py-2.5 text-right"><PpDelta a={sn.margin.current} b={sn.margin.year_ago} /></td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <SourceLine fin={fin} />
    </section>
  )
}

/** Percentage-point change, for ratios where % change would mislead. */
function PpDelta({ a, b }: { a: number | null; b: number | null }) {
  if (a == null || b == null) return <span className="text-ink-3">—</span>
  const d = a - b
  return <span className={d > 0 ? 'text-up' : d < 0 ? 'text-down' : 'text-ink-2'}>{d > 0 ? '+' : d < 0 ? '−' : ''}{Math.abs(d).toFixed(1)}pp</span>
}

function SourceLine({ fin }: { fin: Financials }) {
  return (
    <p className="mt-1.5 text-[11px] text-ink-3">
      Reported figures via <a href={fin.source.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">screener.in</a>, compiled from company filings · fetched {relTime(fin.source.fetched_at)}
    </p>
  )
}

function Observations({ items }: { items: string[] }) {
  if (!items.length) return null
  return (
    <ul className="mt-2 space-y-1.5 text-sm">
      {items.map((o) => <li key={o} className="flex gap-2"><span className="mt-2 size-1 shrink-0 rounded-full bg-ink-3" aria-hidden /><span>{o}</span></li>)}
    </ul>
  )
}

function Trajectory({ fin }: { fin: Financials }) {
  const [view, setView] = useState<'annual' | 'quarterly'>('annual')
  const data = view === 'annual' ? fin.annual : fin.quarterly.slice(-8)
  return (
    <section id="trajectory" className="scroll-mt-28">
      <SectionTitle aside={
        <div className="flex gap-1 text-xs">
          {(['annual', 'quarterly'] as const).map((v) => (
            <button key={v} onClick={() => setView(v)} className={`rounded px-2 py-0.5 ${view === v ? 'bg-surface-2 font-semibold' : 'text-ink-3'}`}>{v}</button>
          ))}
        </div>
      }>Trajectory</SectionTitle>
      <div className="rounded-xl border border-line bg-surface p-3">
        <p className="text-xs font-semibold">Revenue <span className="font-normal text-ink-3">₹ crore</span></p>
        <BarSeries data={data} dataKey="revenue" name="Revenue" />
        {!fin.is_bank && (
          <>
            <p className="mt-3 text-xs font-semibold"><Term k="Margin">EBITDA margin</Term> <span className="font-normal text-ink-3">%</span></p>
            <PctLine data={data} dataKey="margin" name="EBITDA margin" />
          </>
        )}
      </div>
      <Observations items={fin.observations.trajectory} />
    </section>
  )
}

const OUTCOME: Record<Promise_['outcome'], { icon: typeof Check; cls: string }> = {
  Met: { icon: Check, cls: 'text-up' },
  Exceeded: { icon: ArrowUpRight, cls: 'text-up' },
  Missed: { icon: X, cls: 'text-down' },
  'Not yet due': { icon: Clock, cls: 'text-ink-2' },
  "Can't verify": { icon: CircleHelp, cls: 'text-ink-3' },
}

function Ledger({ data, conclusion }: { data?: { rows: Promise_[]; counts: Record<string, number>; transcripts_read: { title: string; url: string }[] }; conclusion: LabelledPoint | null }) {
  const [src, setSrc] = useState<Promise_ | null>(null)
  const grouped = useMemo(() => {
    const m = new Map<string, Promise_[]>()
    for (const r of data?.rows ?? []) m.set(r.said_in, [...(m.get(r.said_in) ?? []), r])
    return [...m.entries()]
  }, [data])
  return (
    <section id="ledger" className="scroll-mt-28">
      <SectionTitle>Promise ledger · narrative vs numbers</SectionTitle>
      {!data ? (
        <EmptyState title="Not built yet">FINN builds this from the last four earnings calls once it has read them.</EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-5 gap-1 text-center">
            {(Object.keys(OUTCOME) as Promise_['outcome'][]).map((o) => {
              const I = OUTCOME[o].icon
              return (
                <div key={o} className="rounded-lg bg-surface-2 px-1 py-2">
                  <div className={`flex items-center justify-center gap-0.5 text-lg font-bold ${OUTCOME[o].cls}`}><I size={13} aria-hidden />{data.counts[o] ?? 0}</div>
                  <div className="text-[10px] leading-tight text-ink-3">{o}</div>
                </div>
              )
            })}
          </div>
          {conclusion && <div className="mt-3 rounded-xl border border-line bg-surface p-3 text-sm"><CitedText segments={[{ text: conclusion.text, citations: conclusion.citations }]} /></div>}
          {data.rows.length === 0 && (
            <p className="mt-3 text-sm text-ink-2">Management made no explicit, quantitative forward-looking commitment in the {data.transcripts_read.length} calls FINN read. Vague optimism isn’t counted as guidance.</p>
          )}
          <div className="mt-3 space-y-4">
            {grouped.map(([said, rows]) => (
              <div key={said}>
                <p className="mb-1.5 text-xs font-semibold text-ink-2">Said on the {said} call</p>
                <ul className="space-y-2">
                  {rows.map((p) => {
                    const o = OUTCOME[p.outcome]
                    const I = o.icon
                    return (
                      <li key={p.id}>
                        <button onClick={() => setSrc(p)} className="block w-full rounded-xl border border-line bg-surface p-3 text-left">
                          <div className="flex items-center gap-2 text-xs">
                            <span className={`inline-flex items-center gap-1 font-semibold ${o.cls}`}><I size={13} aria-hidden />{p.outcome}</span>
                            <span className="text-ink-3">· {p.metric.replace(/_/g, ' ')} · {p.due_period}</span>
                            <span className="ml-auto text-[11px] text-ink-3">p.{p.page}</span>
                          </div>
                          <p className="mt-1.5 text-sm italic leading-snug text-ink-2">“{p.quote}”</p>
                          <p className="mt-1.5 text-xs">{p.explanation}</p>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-ink-3">Quotes are checked word-for-word against the transcript page; outcomes are calculated from reported figures, not judged by the model.</p>
          <SourceSheet cite={src ? { doc_id: src.doc_id, doc_title: src.doc_title, doc_type: 'transcript', period: src.said_in, page: src.page, url: src.doc_url, quote: src.quote } : null}
            onClose={() => setSrc(null)} />
        </>
      )}
    </section>
  )
}

function BullBear({ data }: { data?: NonNullable<CompanyResearch['sections']['bull_bear']>['data'] }) {
  return (
    <section id="case" className="scroll-mt-28">
      <SectionTitle>Bull vs bear</SectionTitle>
      {!data ? (
        <EmptyState title="Not built yet">Each point will cite the filing or financials it rests on.</EmptyState>
      ) : (
        <div className="space-y-3">
          {([['Bull case', data.bull, 'text-up'], ['Bear case', data.bear, 'text-down']] as const).map(([title, pts, cls]) => (
            <div key={title} className="rounded-xl border border-line bg-surface p-3">
              <p className={`text-xs font-semibold ${cls}`}>{title}</p>
              <ul className="mt-2 space-y-2.5 text-sm">
                {pts.map((p, i) => <li key={i}><CitedText segments={[{ text: p.text, citations: p.citations }]} /></li>)}
              </ul>
            </div>
          ))}
          {data.watch && <p className="text-sm"><span className="font-semibold">Dig into next: </span>{data.watch.text}</p>}
          <p className="text-[11px] text-ink-3">
            Written by {data.model} from the documents below only.{data.dropped_uncited > 0 && ` ${data.dropped_uncited} point(s) without a source were removed.`} Not a recommendation.
          </p>
        </div>
      )}
    </section>
  )
}

function Balance({ fin }: { fin: Financials }) {
  const rows = fin.annual.slice(-5)
  return (
    <section id="balance" className="scroll-mt-28">
      <SectionTitle>Balance sheet</SectionTitle>
      {fin.is_bank ? <p className="text-sm text-ink-2">For a bank, borrowings are raw material rather than leverage; asset quality (NPA) in the snapshot is the better lens.</p> : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="num w-full whitespace-nowrap text-xs">
            <thead className="bg-surface-2 text-ink-3"><tr><th className="px-3 py-2 text-left font-medium">FY</th><th className="px-2 py-2 text-right font-medium">Borrowings</th><th className="px-2 py-2 text-right font-medium"><Term k="D/E" /></th><th className="px-2 py-2 text-right font-medium"><Term k="Working capital">WC days</Term></th><th className="px-3 py-2 text-right font-medium"><Term k="ROCE" /></th></tr></thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => (
                <tr key={r.year}><td className="px-3 py-2">{r.label}</td><td className="px-2 py-2 text-right">{amt(r.borrowings)}</td><td className="px-2 py-2 text-right">{r.de == null ? '—' : r.de.toFixed(2)}</td><td className="px-2 py-2 text-right">{r.wc_days ?? '—'}</td><td className="px-3 py-2 text-right">{r.roce == null ? '—' : `${r.roce}%`}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Observations items={fin.observations.balance_sheet} />
    </section>
  )
}

function Cash({ fin }: { fin: Financials }) {
  const rows = fin.annual.slice(-5)
  return (
    <section id="cash" className="scroll-mt-28">
      <SectionTitle>Cash quality</SectionTitle>
      {!fin.is_bank && (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="num w-full whitespace-nowrap text-xs">
            <thead className="bg-surface-2 text-ink-3"><tr><th className="px-3 py-2 text-left font-medium">FY</th><th className="px-2 py-2 text-right font-medium"><Term k="PAT" /> ₹cr</th><th className="px-2 py-2 text-right font-medium"><Term k="CFO" /></th><th className="px-2 py-2 text-right font-medium"><Term k="Cash conversion">CFO/PAT</Term></th><th className="px-3 py-2 text-right font-medium"><Term k="FCF" /></th></tr></thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => (
                <tr key={r.year}><td className="px-3 py-2">{r.label}</td><td className="px-2 py-2 text-right">{amt(r.pat)}</td><td className="px-2 py-2 text-right">{amt(r.cfo)}</td><td className="px-2 py-2 text-right">{r.cfo_to_pat == null ? '—' : `${(r.cfo_to_pat * 100).toFixed(0)}%`}</td><td className={`px-3 py-2 text-right ${r.fcf != null && r.fcf < 0 ? 'text-down' : ''}`}>{amt(r.fcf)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Observations items={fin.observations.cash_quality} />
    </section>
  )
}

function Sources({ symbol, docs, fin, onAdded }: { symbol: string; docs: CompanyResearch['documents']; fin: Financials; onAdded: () => void }) {
  const [mode, setMode] = useState<'none' | 'upload' | 'url'>('none')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const label: Record<string, string> = { annual_report: 'Annual report', transcript: 'Earnings call', results: 'Results', upload: 'Uploaded', filing: 'Filing', presentation: 'Deck' }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    setMsg(null)
    try {
      if (mode === 'upload') {
        f.set('symbol', symbol)
        await api.upload('/api/documents/upload', f)
      } else {
        await api.post('/api/documents/import', { symbol, url: f.get('url'), title: f.get('title'), doc_type: f.get('doc_type'), period: f.get('period') || null })
      }
      setMsg('Added and indexed. Re-run the analysis to include it.')
      setMode('none')
      onAdded()
    } catch (err) {
      setMsg((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section id="sources" className="scroll-mt-28">
      <SectionTitle>Sources FINN read</SectionTitle>
      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface text-sm">
        <li className="flex items-center gap-2 px-3 py-2.5">
          <span className="text-xs text-ink-3">Statements</span>
          <a href={fin.source.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate">Reported financials (screener.in)</a>
          <ExternalLink size={12} className="text-ink-3" aria-hidden />
        </li>
        {docs.map((d) => (
          <li key={d.id} className="flex items-center gap-2 px-3 py-2.5">
            <span className="w-20 shrink-0 text-xs text-ink-3">{label[d.doc_type] ?? d.doc_type}</span>
            <a href={d.source_url.startsWith('upload://') ? undefined : d.source_url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate">{d.title}</a>
            <span className={`shrink-0 text-[11px] ${d.status === 'ready' ? 'text-ink-3' : 'text-down'}`}>
              {d.status === 'ready' ? `${d.pages}p${d.text_quality !== 'good' ? ' · scan' : ''}` : d.status}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[11px] text-ink-3">Primary sources only: the company’s filings, annual reports and call transcripts. No news, broker notes or the model’s own knowledge.</p>
      <div className="mt-3 flex gap-2">
        <button onClick={() => setMode(mode === 'upload' ? 'none' : 'upload')} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-xs"><FileUp size={13} aria-hidden /> Upload PDF</button>
        <button onClick={() => setMode(mode === 'url' ? 'none' : 'url')} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-xs"><Link2 size={13} aria-hidden /> Add by link</button>
      </div>
      {mode !== 'none' && (
        <form onSubmit={submit} className="mt-2 space-y-2 rounded-xl border border-line bg-surface p-3 text-sm">
          {mode === 'upload'
            ? <input name="file" type="file" accept="application/pdf" required className="block w-full text-xs" />
            : <input name="url" type="url" required placeholder="https://… (company or exchange PDF)" className="h-9 w-full rounded-md border border-line bg-surface-2 px-2" />}
          <input name="title" required placeholder="Title, e.g. Q2 FY27 earnings call" className="h-9 w-full rounded-md border border-line bg-surface-2 px-2" />
          <div className="flex gap-2">
            <select name="doc_type" className="h-9 flex-1 rounded-md border border-line bg-surface-2 px-2">
              <option value="transcript">Earnings call</option><option value="annual_report">Annual report</option>
              <option value="results">Results</option><option value="presentation">Investor deck</option><option value="filing">Other filing</option>
            </select>
            <input name="period" placeholder="Period (Q2 FY27)" className="h-9 w-32 rounded-md border border-line bg-surface-2 px-2" />
          </div>
          <button disabled={busy} className="h-9 rounded-lg bg-ink px-4 font-semibold text-page disabled:opacity-50">{busy ? 'Indexing…' : 'Add source'}</button>
        </form>
      )}
      {msg && <p className="mt-2 text-xs text-ink-2" role="status">{msg}</p>}
    </section>
  )
}
