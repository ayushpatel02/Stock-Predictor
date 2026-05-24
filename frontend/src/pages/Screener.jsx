import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchScreener } from '../api/client'

const SIGNAL_BADGES = {
  BUY: 'bg-green-900/60 text-green-300 border-green-700',
  SELL: 'bg-red-900/60 text-red-300 border-red-700',
  HOLD: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
}

const initialFilters = {
  signal: 'ALL',
  minDurability: 0,
  minValuation: 0,
  minMomentum: 0,
  maxRisk: 10,
  minPe: 0,
  maxPe: 200,
  minRsi: 0,
  maxRsi: 100,
}

/**
 * Screener — Trendlyne-style filter + sortable table over the universe.
 *
 * All filters apply additively. The result count updates as you adjust filters.
 */
export default function Screener() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(initialFilters)
  const [sortKey, setSortKey] = useState('momentum')
  const [sortDir, setSortDir] = useState('desc')
  const navigate = useNavigate()

  useEffect(() => {
    fetchScreener()
      .then((d) => setRows(d.rows ?? []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (filters.signal !== 'ALL' && r.signal !== filters.signal) return false
      if ((r.durability ?? 0) < filters.minDurability) return false
      if ((r.valuation ?? 0) < filters.minValuation) return false
      if ((r.momentum ?? 0) < filters.minMomentum) return false
      if ((r.risk_score ?? 10) > filters.maxRisk) return false
      const pe = r.pe_ratio
      if (pe != null && (pe < filters.minPe || pe > filters.maxPe)) return false
      const rsi = r.rsi
      if (rsi != null && (rsi < filters.minRsi || rsi > filters.maxRsi)) return false
      return true
    })
  }, [rows, filters])

  const sorted = useMemo(() => {
    const out = [...filtered]
    out.sort((a, b) => {
      const av = a[sortKey] ?? -Infinity
      const bv = b[sortKey] ?? -Infinity
      const cmp = av > bv ? 1 : av < bv ? -1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
    return out
  }, [filtered, sortKey, sortDir])

  const setSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const Th = ({ k, label, align = 'left' }) => (
    <th
      onClick={() => setSort(k)}
      className={`px-3 py-2 text-${align} font-medium cursor-pointer hover:text-slate-200 select-none`}
    >
      {label} {sortKey === k && (sortDir === 'asc' ? '↑' : '↓')}
    </th>
  )

  const FilterSlider = ({ label, value, onChange, min = 0, max = 100, step = 1 }) => (
    <div>
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span>{label}</span>
        <span className="font-mono text-slate-200">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-indigo-500"
      />
    </div>
  )

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate('/')}
            className="text-xs text-indigo-400 hover:text-indigo-300"
          >
            ← Dashboard
          </button>
          <h1 className="text-2xl font-bold text-slate-100 mt-1">Stock Screener</h1>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-indigo-400">{sorted.length}</div>
          <div className="text-xs text-slate-400">of {rows.length} stocks</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Filters sidebar */}
        <aside className="lg:col-span-1 bg-slate-800 border border-slate-700 rounded-xl p-4 space-y-4 h-fit sticky top-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Filters
          </div>

          {/* Signal filter */}
          <div>
            <div className="text-xs text-slate-400 mb-1">Signal</div>
            <div className="flex flex-wrap gap-1">
              {['ALL', 'BUY', 'HOLD', 'SELL'].map((s) => (
                <button
                  key={s}
                  onClick={() => setFilters((f) => ({ ...f, signal: s }))}
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    filters.signal === s
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <FilterSlider
            label="Min Durability"
            value={filters.minDurability}
            onChange={(v) => setFilters((f) => ({ ...f, minDurability: v }))}
          />
          <FilterSlider
            label="Min Valuation"
            value={filters.minValuation}
            onChange={(v) => setFilters((f) => ({ ...f, minValuation: v }))}
          />
          <FilterSlider
            label="Min Momentum"
            value={filters.minMomentum}
            onChange={(v) => setFilters((f) => ({ ...f, minMomentum: v }))}
          />
          <FilterSlider
            label="Max Risk"
            value={filters.maxRisk}
            onChange={(v) => setFilters((f) => ({ ...f, maxRisk: v }))}
            max={10}
          />
          <FilterSlider
            label="Max P/E"
            value={filters.maxPe}
            onChange={(v) => setFilters((f) => ({ ...f, maxPe: v }))}
            max={200}
          />
          <div>
            <div className="text-xs text-slate-400 mb-1">RSI range</div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                min={0}
                max={100}
                value={filters.minRsi}
                onChange={(e) => setFilters((f) => ({ ...f, minRsi: Number(e.target.value) }))}
                className="bg-slate-700 text-slate-200 text-xs rounded px-2 py-1 border border-slate-600"
                placeholder="Min"
              />
              <input
                type="number"
                min={0}
                max={100}
                value={filters.maxRsi}
                onChange={(e) => setFilters((f) => ({ ...f, maxRsi: Number(e.target.value) }))}
                className="bg-slate-700 text-slate-200 text-xs rounded px-2 py-1 border border-slate-600"
                placeholder="Max"
              />
            </div>
          </div>

          <button
            onClick={() => setFilters(initialFilters)}
            className="w-full mt-2 px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium"
          >
            Reset filters
          </button>
        </aside>

        {/* Results table */}
        <div className="lg:col-span-3 bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Loading screener data…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-slate-400 border-b border-slate-700">
                    <Th k="symbol" label="Symbol" />
                    <Th k="price" label="Price" align="right" />
                    <Th k="day_return" label="Day %" align="right" />
                    <Th k="signal" label="Signal" />
                    <Th k="durability" label="D" align="right" />
                    <Th k="valuation" label="V" align="right" />
                    <Th k="momentum" label="M" align="right" />
                    <Th k="risk_score" label="Risk" align="right" />
                    <Th k="pe_ratio" label="P/E" align="right" />
                    <Th k="rsi" label="RSI" align="right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {sorted.map((row) => {
                    const dayPct = (row.day_return ?? 0) * 100
                    const isUp = dayPct >= 0
                    const sigCls = SIGNAL_BADGES[row.signal] ?? 'bg-slate-700 text-slate-400'
                    return (
                      <tr
                        key={row.symbol}
                        onClick={() => navigate(`/stock/${row.symbol}`)}
                        className="hover:bg-slate-700/50 cursor-pointer transition-colors"
                      >
                        <td className="px-3 py-2 font-mono font-medium text-slate-100">{row.symbol}</td>
                        <td className="px-3 py-2 text-right text-slate-300">₹{row.price?.toFixed(2) ?? '—'}</td>
                        <td className={`px-3 py-2 text-right font-medium ${isUp ? 'text-green-400' : 'text-red-400'}`}>
                          {isUp ? '+' : ''}{dayPct.toFixed(2)}%
                        </td>
                        <td className="px-3 py-2">
                          {row.signal ? (
                            <span className={`px-2 py-0.5 rounded border text-xs font-bold ${sigCls}`}>
                              {row.signal}
                            </span>
                          ) : (
                            <span className="text-slate-500 text-xs">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-slate-300">{row.durability != null ? Math.round(row.durability) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-slate-300">{row.valuation != null ? Math.round(row.valuation) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-slate-300">{row.momentum != null ? Math.round(row.momentum) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-slate-300">{row.risk_score ?? '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-slate-400">{row.pe_ratio != null ? row.pe_ratio.toFixed(1) : '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-slate-400">{row.rsi != null ? row.rsi.toFixed(0) : '—'}</td>
                      </tr>
                    )
                  })}
                  {sorted.length === 0 && (
                    <tr>
                      <td colSpan={10} className="px-4 py-8 text-center text-slate-500 text-sm">
                        No stocks match these filters
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
