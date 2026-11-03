import { ChevronRight, ExternalLink, FileText, Sparkles, UserRound } from 'lucide-react'
import { useState } from 'react'
import type { Announcement, PersonCard, ResultsCard } from '../services/api'
import { categoryLabel, crore, relTime, timeLabel } from '../utils/format'
import { Chip, Delta, PriorityTag, Sheet, Term, cleanTitle } from './ui'

const RAIL: Record<string, string> = { HIGH: 'bg-accent-fill', MEDIUM: 'bg-line-strong', LOW: 'bg-transparent' }

export function AnnouncementCard({ a, compact = false }: { a: Announcement; compact?: boolean }) {
  const [open, setOpen] = useState(false)
  const headline = a.summary?.what_happened ?? cleanTitle(a.title)
  const why = a.summary?.why_it_matters ?? a.priority_reason
  const results = a.card.results
  const people = a.card.people?.filter((p) => p.name)

  return (
    <>
      <article className="relative overflow-hidden rounded-xl border border-line bg-surface">
        <span className={`absolute inset-y-0 left-0 w-[3px] ${RAIL[a.priority]}`} aria-hidden />
        <button onClick={() => setOpen(true)} className="block w-full px-4 pb-3 pt-3 text-left">
          <div className="flex items-center gap-1.5 whitespace-nowrap text-xs text-ink-3">
            <span className="font-semibold text-ink">{a.symbol}</span>
            <span aria-hidden>·</span>
            <span className="min-w-0 truncate">{categoryLabel(a.category)}</span>
            <span aria-hidden>·</span>
            <time dateTime={a.published_at} title={timeLabel(a.published_at)}>{relTime(a.published_at)}</time>
            <span className="ml-auto pl-1"><PriorityTag p={a.priority} /></span>
          </div>
          <h3 className={`mt-1.5 font-semibold leading-snug ${compact ? 'text-sm' : 'text-[15px]'}`}>{headline}</h3>
          {!compact && <p className="mt-1 text-sm leading-snug text-ink-2">{why}</p>}
          {results && !compact && <ResultsStrip r={results} />}
          {people && people.length > 0 && !compact && <PeopleStrip people={people} />}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {a.summary?.is_interpretation && <Chip tone="ai"><Sparkles size={11} aria-hidden /> AI reading</Chip>}
            {a.low_confidence && <Chip tone="warn">Unsure what this is</Chip>}
            {a.related && a.related.length > 0 && <Chip>+{a.related.length} related filing{a.related.length > 1 ? 's' : ''}</Chip>}
            <ChevronRight size={16} className="ml-auto text-ink-3" aria-hidden />
          </div>
        </button>
        {a.pdf_url && (
          <a href={a.pdf_url} target="_blank" rel="noreferrer"
            className="flex items-center gap-1.5 border-t border-line px-4 py-2 text-xs font-medium text-ink-2 hover:text-ink">
            <FileText size={13} aria-hidden /> Original filing on {a.source}
            <ExternalLink size={12} className="ml-auto" aria-hidden />
          </a>
        )}
      </article>
      <Sheet open={open} onClose={() => setOpen(false)} title={<span>{a.company_name} <span className="text-ink-3">· {a.symbol}</span></span>}>
        <FilingDetail a={a} />
      </Sheet>
    </>
  )
}

function ResultsStrip({ r }: { r: ResultsCard }) {
  const rows = ['Revenue', 'EBITDA', 'PBT', 'PAT'].filter((k) => r.metrics[k])
  if (!rows.length) return null
  return (
    <div className="mt-3 grid grid-cols-4 gap-px overflow-hidden rounded-lg border border-line bg-line text-center">
      {rows.map((k) => (
        <div key={k} className="bg-surface-2 px-1 py-2">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-3">{k}</div>
          <div className="mt-0.5 text-xs"><Delta value={r.metrics[k].yoy} digits={1} /></div>
          <div className="text-[10px] text-ink-3">YoY</div>
        </div>
      ))}
    </div>
  )
}

function PeopleStrip({ people }: { people: PersonCard[] }) {
  return (
    <div className="mt-3 space-y-1.5">
      {people.slice(0, 2).map((p) => (
        <div key={p.name + p.role} className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs">
          <UserRound size={14} className="mt-0.5 shrink-0 text-ink-3" aria-hidden />
          <div className="min-w-0">
            <span className="font-semibold">{p.name}</span> <span className="text-ink-2">{p.change} · {p.role}</span>
            {p.background && <p className="mt-0.5 line-clamp-2 text-ink-2">{p.background}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}

export function FilingDetail({ a }: { a: Announcement }) {
  const s = a.summary
  return (
    <div className="space-y-5 text-sm">
      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          <PriorityTag p={a.priority} />
          <Chip>{categoryLabel(a.category)}</Chip>
          {a.low_confidence && <Chip tone="warn">Low-confidence classification</Chip>}
        </div>
        <p className="mt-2 text-[15px] font-semibold leading-snug">{cleanTitle(a.title)}</p>
        <p className="mt-1 text-xs text-ink-3">Filed {timeLabel(a.published_at)} on {a.source}{a.bse_subcategory ? ` · ${a.bse_subcategory}` : ''}</p>
      </div>

      <div className="rounded-lg bg-surface-2 p-3">
        <p className="eyebrow">Why FINN ranked it {a.priority.toLowerCase()}</p>
        <p className="mt-1 text-ink-2">{a.priority_reason}</p>
        <p className="mt-1 text-xs text-ink-3">
          Classified by {a.category_method === 'rules' ? 'filing metadata rules' : a.category_method}, confidence {Math.round(a.category_confidence * 100)}%.
        </p>
      </div>

      {s ? (
        <div className="space-y-3">
          <p className="flex items-center gap-1.5 text-xs text-ink-3"><Sparkles size={12} aria-hidden /> FINN’s reading of the filing — an interpretation, not the company’s words</p>
          {([
            ['What happened', s.what_happened],
            ['Why it matters', s.why_it_matters],
            ['Possible implication', s.implication],
            ['Still unknown', s.unknowns],
          ] as const).map(([k, v]) => (
            <div key={k}>
              <p className="eyebrow">{k}</p>
              <p className="mt-0.5 leading-relaxed">{v}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-ink-3">
          {a.card.needs_reading
            ? a.card.read_error ? `FINN couldn’t read this filing: ${a.card.read_error}` : 'FINN hasn’t read this filing yet. The ranking above comes from its exchange metadata.'
            : 'Routine filing — the headline says everything; FINN didn’t spend a model call on it.'}
        </p>
      )}

      {a.card.results && <ResultsTable r={a.card.results} />}
      {a.card.people && a.card.people.length > 0 && <PeopleDetail people={a.card.people} />}

      <div className="space-y-2">
        {a.pdf_url && (
          <a href={a.pdf_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-lg bg-ink px-3 py-2.5 text-sm font-semibold text-page">
            <FileText size={15} aria-hidden /> Open the original filing <ExternalLink size={13} className="ml-auto" aria-hidden />
          </a>
        )}
        {a.filing_page_url && (
          <a href={a.filing_page_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-lg border border-line px-3 py-2.5 text-sm text-ink-2">
            All {a.symbol} filings on BSE <ExternalLink size={13} className="ml-auto" aria-hidden />
          </a>
        )}
      </div>

      {a.related && a.related.length > 0 && (
        <div>
          <p className="eyebrow">Related filings, same event</p>
          <ul className="mt-1 divide-y divide-line">
            {a.related.map((r) => (
              <li key={r.id} className="py-2">
                <a href={r.pdf_url ?? '#'} target="_blank" rel="noreferrer" className="flex items-start gap-2 text-ink-2">
                  <span className="flex-1">{cleanTitle(r.title)}</span>
                  <ExternalLink size={12} className="mt-1 shrink-0" aria-hidden />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function ResultsTable({ r }: { r: ResultsCard }) {
  const keys = ['Revenue', 'EBITDA', 'PBT', 'PAT'].filter((k) => r.metrics[k])
  return (
    <div>
      <p className="eyebrow">First cut of the numbers{r.period_label ? ` · ${r.period_label}` : ''}</p>
      <p className="mt-0.5 text-xs text-ink-3">
        {r.basis ? `${r.basis[0].toUpperCase()}${r.basis.slice(1)}` : 'Basis not stated'}, ₹ crore{r.page ? ` · from page ${r.page} of the filing` : ''}
      </p>
      <div className="mt-2 overflow-hidden rounded-lg border border-line">
        <table className="num w-full text-xs">
          <thead className="bg-surface-2 text-ink-3">
            <tr>
              <th className="px-2 py-1.5 text-left font-medium"></th>
              <th className="px-2 py-1.5 text-right font-medium">This qtr</th>
              <th className="px-2 py-1.5 text-right font-medium"><Term k="QoQ" /></th>
              <th className="px-2 py-1.5 text-right font-medium"><Term k="YoY" /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {keys.map((k) => {
              const m = r.metrics[k]
              return (
                <tr key={k}>
                  <td className="px-2 py-2 text-left font-medium"><Term k={k} />{m.derived && <span className="ml-1 text-ink-3" title={m.derived}>*</span>}</td>
                  <td className="px-2 py-2 text-right">{crore(m.current)}</td>
                  <td className="px-2 py-2 text-right"><Delta value={m.qoq} digits={1} /></td>
                  <td className="px-2 py-2 text-right"><Delta value={m.yoy} digits={1} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {keys.some((k) => r.metrics[k].derived) && (
        <p className="mt-1 text-[11px] text-ink-3">* {keys.map((k) => r.metrics[k].derived).filter(Boolean)[0]}</p>
      )}
      {r.checks.length > 0 && (
        <ul className="mt-2 space-y-1 text-[11px] text-ink-3">
          {r.checks.map((c) => <li key={c}>· {c}</li>)}
        </ul>
      )}
      {r.promise_checks && r.promise_checks.length > 0 && (
        <div className="mt-3 rounded-lg border border-line p-3">
          <p className="eyebrow">Against what management promised</p>
          <ul className="mt-1.5 space-y-2">
            {r.promise_checks.map((p) => (
              <li key={p.quote} className="text-xs">
                <span className="font-semibold">{p.outcome}</span> · {p.metric}: {p.target_text}
                <p className="text-ink-2">{p.explanation}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function PeopleDetail({ people }: { people: PersonCard[] }) {
  return (
    <div>
      <p className="eyebrow">Who</p>
      <ul className="mt-1 space-y-2">
        {people.map((p) => (
          <li key={p.name + p.role} className="rounded-lg border border-line p-3">
            <p className="font-semibold">{p.name}</p>
            <p className="text-xs text-ink-2">{p.change} · {p.role}{p.effective ? ` · effective ${p.effective}` : ''}</p>
            <p className="mt-1.5 leading-relaxed">
              {p.background ?? <span className="text-ink-3">The filing doesn’t include a background for this person.</span>}
            </p>
            <p className="mt-1 text-[11px] text-ink-3">{p.background_source === 'filing' ? 'Background as disclosed in the filing.' : ''}</p>
            <a href={p.linkedin_search_url} target="_blank" rel="noreferrer" className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-ink-2 underline underline-offset-2">
              Look up on LinkedIn <ExternalLink size={11} aria-hidden />
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
