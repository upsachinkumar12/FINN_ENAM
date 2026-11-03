const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
const inr0 = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

export const price = (v: number | null | undefined) => (v == null ? '—' : `₹${inr.format(v)}`)

/** Indian convention: crores for company financials (Screener reports in ₹ crore). */
export const crore = (v: number | null | undefined) => (v == null ? '—' : `₹${inr0.format(v)} cr`)

/** A bare ₹ crore amount for tables whose header already states the unit. */
export const amt = (v: number | null | undefined) => (v == null ? '—' : inr0.format(v))

export function pct(v: number | null | undefined, digits = 1) {
  if (v == null || !Number.isFinite(v)) return '—'
  const s = v.toFixed(digits)
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${s.replace('-', '')}%`
}

export function compactVolume(v: number | null | undefined) {
  if (v == null) return '—'
  if (v >= 1e7) return `${(v / 1e7).toFixed(2)} cr`
  if (v >= 1e5) return `${(v / 1e5).toFixed(1)} lakh`
  return inr0.format(v)
}

export function multiple(v: number | null | undefined) {
  return v == null ? '—' : `${v.toFixed(1)}×`
}

export function relTime(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return 'never'
  const t = new Date(iso).getTime()
  const m = Math.round((now - t) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  return d === 1 ? 'yesterday' : `${d}d ago`
}

export function dateLabel(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export function timeLabel(iso: string) {
  return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
}

export const CATEGORY_LABEL: Record<string, string> = {
  results: 'Results',
  'M&A': 'M&A',
  fund_raise: 'Fund raise',
  management_change: 'Management',
  litigation: 'Legal & regulatory',
  insider_trading: 'Insider / promoter',
  earnings_call: 'Earnings call',
  investor_meetings: 'Investor meetings',
  credit_rating: 'Credit rating',
  dividend: 'Dividend',
  bonus_split: 'Bonus / split',
  capex: 'Capex',
  press_release: 'Press release',
  postal_ballot: 'Postal ballot',
  agm_egm: 'AGM / EGM',
  pledging: 'Pledging',
  unclassified: 'Routine',
}

export const categoryLabel = (c: string) => CATEGORY_LABEL[c] ?? c
