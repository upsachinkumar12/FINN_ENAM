import { AlertTriangle, ArrowDownRight, ArrowUpRight, Inbox, RotateCw } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import type { Priority } from '../services/api'
import { pct } from '../utils/format'
import { GLOSSARY } from '../utils/glossary'

export function Delta({ value, digits = 2, className = '' }: { value: number | null | undefined; digits?: number; className?: string }) {
  if (value == null) return <span className={`num text-ink-3 ${className}`}>—</span>
  const up = value > 0
  const flat = value === 0
  const Icon = up ? ArrowUpRight : ArrowDownRight
  return (
    <span className={`num inline-flex items-center gap-0.5 ${flat ? 'text-ink-2' : up ? 'text-up' : 'text-down'} ${className}`}>
      {!flat && <Icon size={14} strokeWidth={2.25} aria-hidden />}
      {pct(value, digits)}
    </span>
  )
}

export function Spark({ values, width = 64, height = 22 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return <span style={{ width, height }} className="inline-block" />
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * width},${height - 2 - ((v - min) / span) * (height - 4)}`)
  const up = values[values.length - 1] >= values[0]
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden className="shrink-0">
      <polyline points={pts.join(' ')} fill="none" stroke={up ? 'var(--up)' : 'var(--down)'} strokeWidth={1.5}
        strokeLinejoin="round" strokeLinecap="round" opacity={0.9} />
    </svg>
  )
}

const PRIORITY_STYLE: Record<Priority, string> = {
  HIGH: 'bg-accent-fill text-[#0b0b0b]',
  MEDIUM: 'border border-line-strong text-ink-2',
  LOW: 'text-ink-3',
}
const PRIORITY_TEXT: Record<Priority, string> = { HIGH: 'Must read', MEDIUM: 'Worth a look', LOW: 'Routine' }

export function PriorityTag({ p }: { p: Priority }) {
  return (
    <span className={`inline-flex h-5 shrink-0 items-center whitespace-nowrap rounded px-1.5 text-[11px] font-semibold ${PRIORITY_STYLE[p]}`}>
      {PRIORITY_TEXT[p]}
    </span>
  )
}

export function Chip({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'warn' | 'ai' }) {
  const t = tone === 'warn' ? 'bg-accent-wash text-accent' : tone === 'ai' ? 'border border-line text-ink-3' : 'bg-surface-2 text-ink-2'
  return <span className={`inline-flex h-5 items-center gap-1 rounded px-1.5 text-[11px] font-medium ${t}`}>{children}</span>
}

/** A finance term with a tap-to-reveal plain-English definition (from ENAM's reference document). */
export function Term({ k, children }: { k: string; children?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  const def = GLOSSARY[k]
  if (!def) return <>{children ?? k}</>
  return (
    <span ref={ref} className="relative inline-block">
      <button type="button" onClick={(e) => { e.stopPropagation(); setOpen((o) => !o) }}
        className="cursor-help underline decoration-dotted decoration-ink-3 underline-offset-2" aria-expanded={open}>
        {children ?? k}
      </button>
      {open && (
        <span role="tooltip" className="absolute left-0 top-full z-30 mt-1 w-64 rounded-lg border border-line bg-surface p-3 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-ink-2 shadow-lg">
          <span className="mb-1 block font-semibold text-ink">{k}</span>
          {def}
        </span>
      )}
    </span>
  )
}

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center" role="dialog" aria-modal="true">
      <button className="absolute inset-0 bg-[var(--scrim)]" aria-label="Close" onClick={onClose} />
      <div className="sheet-in pb-safe relative max-h-[88dvh] w-full max-w-xl overflow-y-auto rounded-t-2xl border border-line bg-surface">
        <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
          <div className="min-w-0 text-sm font-semibold">{title}</div>
          <button onClick={onClose} className="rounded-md px-2 py-1 text-sm text-ink-2 hover:bg-surface-2">Done</button>
        </div>
        <div className="px-4 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  )
}

export function SkeletonRows({ n = 4, h = 64 }: { n?: number; h?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" style={{ height: h }} />)}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 text-sm">
      <div className="flex items-start gap-2">
        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium">Couldn’t load this</p>
          <p className="mt-0.5 text-ink-2">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-surface-2 px-3 py-1.5 text-sm font-medium">
          <RotateCw size={14} aria-hidden /> Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line p-5 text-center text-sm">
      <Inbox size={20} className="mx-auto text-ink-3" aria-hidden />
      <p className="mt-2 font-medium">{title}</p>
      {children && <div className="mt-1 text-ink-2">{children}</div>}
    </div>
  )
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg bg-surface-2 p-0.5">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={`h-7 rounded-md px-2.5 text-xs font-medium transition-colors ${value === o.value ? 'bg-surface text-ink shadow-sm' : 'text-ink-2'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-2 mt-6 flex items-baseline justify-between gap-2">
      <h2 className="eyebrow">{children}</h2>
      {aside}
    </div>
  )
}

/** Strips the boilerplate BSE prefixes so the headline starts with what happened. */
export function cleanTitle(t: string) {
  return t
    .replace(/^Announcement under Regulation 30 \(LODR\)-/i, '')
    .replace(/^Board Meeting Outcome for /i, 'Board outcome: ')
    .replace(/^Press Release\s*-\s*/i, '')
    .replace(/_/g, ' ')
    .replace(/''/g, '’')
    .trim()
}
