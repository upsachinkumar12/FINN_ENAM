import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const axis = { stroke: 'var(--axis)', tick: { fill: 'var(--ink-3)', fontSize: 11 }, tickLine: false }

function Tip({ active, payload, label, unit }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string; unit: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs shadow-lg">
      <p className="font-semibold">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="num text-ink-2">{p.name}: {p.value == null ? '—' : unit === '%' ? `${p.value.toFixed(1)}%` : `₹${inr.format(p.value)} cr`}</p>
      ))}
    </div>
  )
}

/** One measure, one axis. Bars are anchored to zero with rounded data ends. */
export function BarSeries({ data, dataKey, name, height = 160 }: { data: Record<string, unknown>[]; dataKey: string; name: string; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label={`${name} by period`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, left: -8, bottom: 0 }} barCategoryGap={4}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="label" {...axis} interval="preserveStartEnd" minTickGap={8} />
          <YAxis {...axis} width={52} tickFormatter={(v: number) => (Math.abs(v) >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : inr.format(v))} />
          <Tooltip content={<Tip unit="cr" />} cursor={{ fill: 'var(--surface-2)' }} />
          <Bar dataKey={dataKey} name={name} fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function PctLine({ data, dataKey, name, height = 120 }: { data: Record<string, unknown>[]; dataKey: string; name: string; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label={`${name} by period`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="label" {...axis} interval="preserveStartEnd" minTickGap={8} />
          <YAxis {...axis} width={40} tickFormatter={(v: number) => `${v}%`} domain={['auto', 'auto']} />
          <Tooltip content={<Tip unit="%" />} cursor={{ stroke: 'var(--line-strong)' }} />
          <Line dataKey={dataKey} name={name} stroke="var(--series-2)" strokeWidth={2} dot={{ r: 3, strokeWidth: 0, fill: 'var(--series-2)' }}
            activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2 }} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
