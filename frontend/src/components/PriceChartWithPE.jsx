import { useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
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
 * PriceChartWithPE — Dual-axis chart: price area (left) + PE line (right).
 *
 * Props:
 *   peHistory — array of {date, close, pe} from /overview endpoint
 */
export default function PriceChartWithPE({ peHistory }) {
  const [period, setPeriod] = useState('1y')
  const filtered = filterByPeriod(peHistory ?? [], period)

  if (!filtered.length) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-500 text-sm">
        No price data available
      </div>
    )
  }

  const prices = filtered.map((d) => d.close)
  const minPrice = Math.min(...prices) * 0.98
  const maxPrice = Math.max(...prices) * 1.02
  const isUp = prices[prices.length - 1] >= prices[0]

  const pes = filtered.map((d) => d.pe).filter(Boolean)
  const minPe = pes.length ? Math.min(...pes) * 0.95 : 0
  const maxPe = pes.length ? Math.max(...pes) * 1.05 : 100
  const hasPe = pes.length > 0

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs space-y-1">
        <div className="text-slate-400">{label}</div>
        {payload.map((p, i) => (
          <div key={i} style={{ color: p.color }} className="flex gap-2 justify-between">
            <span>{p.name}:</span>
            <span className="font-mono font-semibold">
              {p.name === 'Price' ? `₹${p.value?.toFixed(2)}` : p.value?.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div>
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

      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={filtered} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="peChartGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={isUp ? '#6366f1' : '#ef4444'} stopOpacity={0.25} />
              <stop offset="95%" stopColor={isUp ? '#6366f1' : '#ef4444'} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickFormatter={(d) => d.slice(0, 7)}
            interval="preserveStartEnd"
          />
          {/* Left axis: price */}
          <YAxis
            yAxisId="price"
            domain={[minPrice, maxPrice]}
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickFormatter={(v) => `₹${v.toFixed(0)}`}
            width={64}
          />
          {/* Right axis: PE */}
          {hasPe && (
            <YAxis
              yAxisId="pe"
              orientation="right"
              domain={[minPe, maxPe]}
              tick={{ fill: '#f59e0b', fontSize: 11 }}
              tickFormatter={(v) => `${v.toFixed(0)}x`}
              width={40}
            />
          )}
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
            formatter={(v) => <span style={{ color: '#94a3b8' }}>{v}</span>}
          />
          <Area
            yAxisId="price"
            type="monotone"
            dataKey="close"
            name="Price"
            stroke={isUp ? '#6366f1' : '#ef4444'}
            strokeWidth={2}
            fill="url(#peChartGradient)"
            dot={false}
            activeDot={{ r: 4 }}
          />
          {hasPe && (
            <Line
              yAxisId="pe"
              type="monotone"
              dataKey="pe"
              name="P/E"
              stroke="#f59e0b"
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3 }}
              strokeDasharray="4 2"
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
      {hasPe && (
        <div className="text-xs text-slate-500 text-right mt-1">
          Dashed line = trailing P/E ratio (right axis)
        </div>
      )}
    </div>
  )
}
