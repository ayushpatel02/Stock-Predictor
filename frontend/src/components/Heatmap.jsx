import { useNavigate } from 'react-router-dom'

/**
 * Heatmap — colored grid of all symbols, sized by market cap, colored by metric.
 *
 * Like Trendlyne's sector heatmap. The selected metric drives the color:
 *   day_return: green for gainers, red for losers
 *   momentum:   green for high momentum, red for weak
 *   signal:     buy/hold/sell color coded
 *
 * Props:
 *   rows — array from /screener/all
 *   metric — 'day_return' | 'momentum' | 'signal' | 'durability' | 'valuation'
 */
function colorFor(metric, row) {
  if (metric === 'signal') {
    if (row.signal === 'BUY') return { bg: '#14532d', text: '#86efac' }
    if (row.signal === 'SELL') return { bg: '#7f1d1d', text: '#fca5a5' }
    return { bg: '#451a03', text: '#fcd34d' }
  }
  if (metric === 'day_return') {
    const r = (row.day_return ?? 0) * 100
    if (r > 2) return { bg: '#14532d', text: '#86efac' }
    if (r > 0.5) return { bg: '#166534', text: '#bbf7d0' }
    if (r > 0) return { bg: '#1e3a2a', text: '#a7f3d0' }
    if (r > -0.5) return { bg: '#3a1e1e', text: '#fecaca' }
    if (r > -2) return { bg: '#7f1d1d', text: '#fecaca' }
    return { bg: '#991b1b', text: '#fee2e2' }
  }
  // For DVM-like scores 0-100
  const v = row[metric] ?? 50
  if (v >= 70) return { bg: '#14532d', text: '#86efac' }
  if (v >= 55) return { bg: '#166534', text: '#bbf7d0' }
  if (v >= 40) return { bg: '#78350f', text: '#fcd34d' }
  if (v >= 25) return { bg: '#7c2d12', text: '#fecaca' }
  return { bg: '#7f1d1d', text: '#fecaca' }
}

function metricValue(metric, row) {
  if (metric === 'signal') return row.signal ?? '—'
  if (metric === 'day_return') {
    const r = (row.day_return ?? 0) * 100
    return `${r >= 0 ? '+' : ''}${r.toFixed(2)}%`
  }
  const v = row[metric]
  return v != null ? Math.round(v) : '—'
}

const METRICS = [
  { value: 'day_return', label: 'Day %' },
  { value: 'signal', label: 'Signal' },
  { value: 'momentum', label: 'Momentum' },
  { value: 'durability', label: 'Durability' },
  { value: 'valuation', label: 'Valuation' },
]

export default function Heatmap({ rows, metric, onMetricChange }) {
  const navigate = useNavigate()

  if (!rows?.length) {
    return (
      <div className="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-1">
        {Array.from({ length: 50 }).map((_, i) => (
          <div key={i} className="aspect-square bg-slate-800 rounded animate-pulse" />
        ))}
      </div>
    )
  }

  // Sort by market cap descending so largest are first
  const sorted = [...rows].sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0))

  return (
    <div>
      {/* Metric selector */}
      <div className="flex flex-wrap gap-2 mb-3">
        {METRICS.map((m) => (
          <button
            key={m.value}
            onClick={() => onMetricChange(m.value)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              metric === m.value
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-1">
        {sorted.map((row) => {
          const c = colorFor(metric, row)
          return (
            <button
              key={row.symbol}
              onClick={() => navigate(`/stock/${row.symbol}`)}
              className="aspect-square rounded p-1 flex flex-col items-center justify-center hover:ring-2 hover:ring-indigo-400 transition-all overflow-hidden"
              style={{ backgroundColor: c.bg }}
              title={`${row.symbol} · ${metricValue(metric, row)}`}
            >
              <div
                className="text-[10px] sm:text-[11px] font-bold leading-tight truncate w-full text-center"
                style={{ color: c.text }}
              >
                {row.symbol}
              </div>
              <div
                className="text-[9px] sm:text-[10px] font-mono mt-0.5"
                style={{ color: c.text }}
              >
                {metricValue(metric, row)}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
