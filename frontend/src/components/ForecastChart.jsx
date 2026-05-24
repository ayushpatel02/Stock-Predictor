import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

/**
 * ForecastChart — bar chart for revenue or EPS forecasts.
 *
 * Actual years: solid indigo bars.
 * Estimated years: lighter teal bars with "E" label.
 *
 * Props:
 *   title      — section heading
 *   actuals    — array of {year, value}
 *   estimates  — array of {year, value}
 *   formatValue — (value) => string for Y-axis + tooltip
 */
export default function ForecastChart({ title, actuals = [], estimates = [], formatValue }) {
  const fmt = formatValue || ((v) => v?.toLocaleString('en-IN') ?? '—')

  if (!actuals.length && !estimates.length) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{title}</div>
        <div className="text-sm text-slate-500 py-4 text-center">No forecast data available</div>
      </div>
    )
  }

  // Combine and tag each bar
  const combined = [
    ...actuals.map((d) => ({ ...d, type: 'actual' })),
    ...estimates.map((d) => ({ ...d, type: 'estimate' })),
  ]

  // Compute YoY growth for label
  const withGrowth = combined.map((d, i) => {
    const prev = combined[i - 1]
    const growth = prev && prev.value ? ((d.value - prev.value) / Math.abs(prev.value)) * 100 : null
    return { ...d, growth }
  })

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    const d = payload[0]?.payload
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs">
        <div className="text-slate-400 mb-1">{label} {d?.type === 'estimate' ? '(Estimate)' : '(Actual)'}</div>
        <div className="text-slate-100 font-mono font-semibold">{fmt(d?.value)}</div>
        {d?.growth != null && (
          <div className={`mt-0.5 ${d.growth >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            YoY: {d.growth >= 0 ? '+' : ''}{d.growth.toFixed(1)}%
          </div>
        )}
      </div>
    )
  }

  const maxVal = Math.max(...combined.map((d) => Math.abs(d.value || 0)))

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</div>
        <div className="flex gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2 rounded-sm bg-indigo-500" /> Actual
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-2 rounded-sm bg-teal-500 opacity-60" /> Estimate
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={withGrowth} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
          <XAxis dataKey="year" tick={{ fill: '#64748b', fontSize: 11 }} />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickFormatter={(v) => fmt(v)}
            width={72}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(99,102,241,0.08)' }} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {withGrowth.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.type === 'actual' ? '#6366f1' : '#14b8a6'}
                opacity={entry.type === 'estimate' ? 0.6 : 1}
              />
            ))}
            <LabelList
              dataKey="growth"
              position="top"
              formatter={(v) => (v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(0)}%` : '')}
              style={{ fill: '#64748b', fontSize: 10 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
