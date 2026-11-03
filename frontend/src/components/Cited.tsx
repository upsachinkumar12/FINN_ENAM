import { ExternalLink, FileText } from 'lucide-react'
import { useState } from 'react'
import type { CitedSegment } from '../services/api'
import { Sheet } from './ui'

type Cite = CitedSegment['citations'][number]

const DOC_TYPE: Record<string, string> = {
  annual_report: 'Annual report', transcript: 'Earnings call', results: 'Results filing',
  financials: 'Reported statements', presentation: 'Investor deck', filing: 'Filing', upload: 'Uploaded PDF',
}

/** Prose with numbered source markers. Tapping a marker opens the exact passage, page and link. */
export function CitedText({ segments, className = '' }: { segments: CitedSegment[]; className?: string }) {
  const [open, setOpen] = useState<Cite | null>(null)
  const all: Cite[] = []
  const keyOf = (c: Cite) => `${c.doc_id}|${c.page}|${c.quote.slice(0, 40)}`
  const order = new Map<string, number>()
  for (const s of segments) for (const c of s.citations) if (!order.has(keyOf(c))) { order.set(keyOf(c), all.length + 1); all.push(c) }

  return (
    <>
      <p className={`leading-relaxed ${className}`}>
        {segments.map((s, i) => (
          <span key={i}>
            {s.text}
            {s.citations.map((c) => (
              <button key={keyOf(c)} onClick={() => setOpen(c)} aria-label={`Source ${order.get(keyOf(c))}: ${c.doc_title}${c.page ? `, page ${c.page}` : ''}`}
                className="mx-0.5 inline-grid h-4 min-w-4 place-items-center rounded bg-surface-2 px-1 align-text-top text-[10px] font-semibold text-ink-2 hover:bg-line">
                {order.get(keyOf(c))}
              </button>
            ))}
          </span>
        ))}
      </p>
      <SourceSheet cite={open} onClose={() => setOpen(null)} />
    </>
  )
}

export function SourceSheet({ cite, onClose }: { cite: Cite | null; onClose: () => void }) {
  return (
    <Sheet open={!!cite} onClose={onClose} title="Source">
      {cite && (
        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-2">
            <FileText size={16} className="mt-0.5 shrink-0 text-ink-3" aria-hidden />
            <div>
              <p className="font-semibold">{cite.doc_title}</p>
              <p className="text-xs text-ink-3">
                {DOC_TYPE[cite.doc_type] ?? cite.doc_type}{cite.period ? ` · ${cite.period}` : ''}{cite.page ? ` · page ${cite.page}` : ''}
              </p>
            </div>
          </div>
          <blockquote className="border-l-2 border-accent-fill pl-3 leading-relaxed text-ink-2">“{cite.quote.trim()}”</blockquote>
          <p className="text-xs text-ink-3">Exact passage from the document, located by FINN’s index — not reworded by the model.</p>
          {cite.url && (
            <a href={cite.url.startsWith('upload://') ? undefined : cite.url} target="_blank" rel="noreferrer"
              className="flex items-center gap-2 rounded-lg bg-ink px-3 py-2.5 font-semibold text-page">
              Open document{cite.page ? ` (page ${cite.page})` : ''} <ExternalLink size={13} className="ml-auto" aria-hidden />
            </a>
          )}
        </div>
      )}
    </Sheet>
  )
}
