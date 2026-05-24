import { useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const PERIODS = ['1m', '3m', '6m', '1y']

function filterByPeriod(data, period) {
  if (!data?.length) return []
  const now = new Date(data[data.length - 1].date)
  const months = { '1m': 1, '3m': 3, '6m': 6, '1y': 12 }[period] ?? 12
  const cutoff = new Date(now)
  cutoff.setMonth(cutoff.getMonth() - months)
  return data.filter((d) => new Date(d.date) >= cutoff)
}

/**
 * PriceChart — Recharts area chart for OHLCV close prices.
 *
 * Props:
 *   data — array of {date, open, high, low, close, volume}
 */
export default function PriceChart({ data }) {
  const [period, setPeriod] = useState('1y')
  const filtered = filterByPeriod(data, period)

  if (!filtered.length) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-500 text-sm">
        No price data available
      </div>
    )
  }

  const prices = filtered.map((d) => d.close)
  const minY = Math.min(...prices) * 0.99
  const maxY = Math.max(...prices) * 1.01
  const isUp = prices[prices.length - 1] >= prices[0]

  return (
    <div>
      {/* Period selector */}
      <div className="flex gap-2 mb-3 justify-end">
        {PERIODS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              period === p
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {p.toUpperCase()}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={filtered} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor={isUp ? '#6366f1' : '#ef4444'}
                stopOpacity={0.3}
              />
              <stop
                offset="95%"
                stopColor={isUp ? '#6366f1' : '#ef4444'}
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickFormatter={(d) => d.slice(0, 7)}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minY, maxY]}
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickFormatter={(v) => `₹${v.toFixed(0)}`}
            width={64}
          />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
            labelStyle={{ color: '#94a3b8', fontSize: 12 }}
            formatter={(v) => [`₹${v.toFixed(2)}`, 'Close']}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke={isUp ? '#6366f1' : '#ef4444'}
            strokeWidth={2}
            fill="url(#priceGradient)"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
