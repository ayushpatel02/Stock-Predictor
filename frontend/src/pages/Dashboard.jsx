import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchMarketOverview, fetchScreener } from '../api/client'
import Heatmap from '../components/Heatmap.jsx'
import MarketOverview from '../components/MarketOverview.jsx'

const SIGNAL_BADGES = {
  BUY: 'bg-green-900/60 text-green-300 border-green-700',
  SELL: 'bg-red-900/60 text-red-300 border-red-700',
  HOLD: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
}

function WatchlistTable({ rows }) {
  const navigate = useNavigate()
  const [sortKey, setSortKey] = useState('symbol')
  const [sortDir, setSortDir] = useState('asc')

  const sorted = useMemo(() => {
    const out = [...(rows ?? [])]
    out.sort((a, b) => {
      const av = a[sortKey] ?? -Infinity
      const bv = b[sortKey] ?? -Infinity
      const cmp = av > bv ? 1 : av < bv ? -1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
    return out
  }, [rows, sortKey, sortDir])

  const setSort = (key) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const Th = ({ k, label, align = 'left' }) => (
    <th
      onClick={() => setSort(k)}
      className={`px-3 py-2 text-${align} font-medium cursor-pointer hover:text-slate-200 select-none`}
    >
      {label} {sortKey === k && (sortDir === 'asc' ? '↑' : '↓')}
    </th>
  )

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-slate-400 border-b border-slate-700">
            <Th k="symbol" label="Symbol" />
            <Th k="price" label="Price" align="right" />
            <Th k="day_return" label="Day %" align="right" />
            <Th k="signal" label="Signal" />
            <Th k="probability_up" label="Prob ↑" align="right" />
            <Th k="durability" label="D" align="right" />
            <Th k="valuation" label="V" align="right" />
            <Th k="momentum" label="M" align="right" />
            <Th k="risk_score" label="Risk" align="right" />
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
                <td className="px-3 py-2 font-mono font-medium text-slate-100">
                  {row.symbol}
                </td>
                <td className="px-3 py-2 text-right text-slate-300">
                  ₹{row.price?.toFixed(2) ?? '—'}
                </td>
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
                <td className="px-3 py-2 text-right text-slate-300 font-mono text-xs">
                  {row.probability_up != null ? `${(row.probability_up * 100).toFixed(0)}%` : '—'}
                </td>
                <td className="px-3 py-2 text-right text-slate-300 font-mono">
                  {row.durability != null ? Math.round(row.durability) : '—'}
                </td>
                <td className="px-3 py-2 text-right text-slate-300 font-mono">
                  {row.valuation != null ? Math.round(row.valuation) : '—'}
                </td>
                <td className="px-3 py-2 text-right text-slate-300 font-mono">
                  {row.momentum != null ? Math.round(row.momentum) : '—'}
                </td>
                <td className="px-3 py-2 text-right text-slate-300 font-mono">
                  {row.risk_score ?? '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Dashboard() {
  const [market, setMarket] = useState(null)
  const [marketLoading, setMarketLoading] = useState(true)
  const [screener, setScreener] = useState(null)
  const [screenerLoading, setScreenerLoading] = useState(true)
  const [view, setView] = useState('heatmap')
  const [heatmapMetric, setHeatmapMetric] = useState('day_return')

  useEffect(() => {
    fetchMarketOverview()
      .then(setMarket)
      .catch(() => setMarket(null))
      .finally(() => setMarketLoading(false))

    fetchScreener()
      .then((d) => setScreener(d.rows ?? []))
      .catch(() => setScreener([]))
      .finally(() => setScreenerLoading(false))
  }, [])

  // Aggregate signals for the summary chips
  const summary = useMemo(() => {
    if (!screener) return null
    const buys = screener.filter((r) => r.signal === 'BUY').length
    const sells = screener.filter((r) => r.signal === 'SELL').length
    const holds = screener.filter((r) => r.signal === 'HOLD').length
    const gainers = screener.filter((r) => (r.day_return ?? 0) > 0).length
    return { buys, sells, holds, gainers, total: screener.length }
  }, [screener])

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Market overview */}
      <section>
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Market Overview
        </h2>
        {marketLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="bg-slate-800 rounded-xl h-20 animate-pulse border border-slate-700" />
            ))}
          </div>
        ) : (
          <MarketOverview data={market} />
        )}
      </section>

      {/* Summary chips */}
      {summary && (
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-3">
            <div className="text-xs text-slate-400">Buy Signals</div>
            <div className="text-2xl font-bold text-green-400 mt-1">{summary.buys}</div>
          </div>
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-3">
            <div className="text-xs text-slate-400">Hold</div>
            <div className="text-2xl font-bold text-yellow-400 mt-1">{summary.holds}</div>
          </div>
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-3">
            <div className="text-xs text-slate-400">Sell Signals</div>
            <div className="text-2xl font-bold text-red-400 mt-1">{summary.sells}</div>
          </div>
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-3">
            <div className="text-xs text-slate-400">Gainers Today</div>
            <div className="text-2xl font-bold text-slate-200 mt-1">
              {summary.gainers} / {summary.total}
            </div>
          </div>
        </section>
      )}

      {/* Heatmap / Table toggle */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
            Nifty 50
          </h2>
          <div className="flex items-center gap-2">
            <Link
              to="/screener"
              className="text-xs text-indigo-400 hover:text-indigo-300 mr-2"
            >
              Advanced screener →
            </Link>
            <div className="flex bg-slate-800 rounded border border-slate-700 overflow-hidden">
              <button
                onClick={() => setView('heatmap')}
                className={`px-3 py-1 text-xs font-medium ${
                  view === 'heatmap' ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                Heatmap
              </button>
              <button
                onClick={() => setView('table')}
                className={`px-3 py-1 text-xs font-medium ${
                  view === 'table' ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-700'
                }`}
              >
                Table
              </button>
            </div>
          </div>
        </div>

        {screenerLoading ? (
          <div className="bg-slate-800 rounded-xl border border-slate-700 h-64 animate-pulse" />
        ) : view === 'heatmap' ? (
          <Heatmap
            rows={screener}
            metric={heatmapMetric}
            onMetricChange={setHeatmapMetric}
          />
        ) : (
          <WatchlistTable rows={screener} />
        )}

        <p className="text-xs text-slate-500 mt-3">
          ML signals require trained models — run{' '}
          <code className="font-mono bg-slate-800 px-1 rounded">python -m app.scripts.train_all</code>{' '}
          to populate them.
        </p>
      </section>
    </div>
  )
}
