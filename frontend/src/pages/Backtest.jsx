import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { runBacktest } from '../api/client'

function MetricsTable({ metrics }) {
  if (!metrics) return null
  const rows = [
    ['Total Return', `${(metrics.total_return * 100).toFixed(2)}%`],
    ['Alpha vs Buy-Hold', `${(metrics.alpha * 100).toFixed(2)}%`],
    ['Sharpe Ratio', metrics.sharpe_ratio?.toFixed(3) ?? '—'],
    ['Max Drawdown', `${(metrics.max_drawdown * 100).toFixed(2)}%`],
    ['Win Rate', `${(metrics.win_rate * 100).toFixed(1)}%`],
    ['Number of Trades', metrics.num_trades],
    ['Buy-Hold Return', `${(metrics.buy_hold_return * 100).toFixed(2)}%`],
  ]

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase">
        Performance Metrics
      </div>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-slate-700">
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td className="px-4 py-2 text-slate-400">{label}</td>
              <td className="px-4 py-2 text-slate-100 text-right font-mono">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EquityChart({ equityCurve }) {
  const data = Object.entries(equityCurve ?? {}).map(([date, value]) => ({
    date,
    strategy: Math.round(value),
  }))

  if (!data.length) return <div className="text-slate-500 text-sm">No equity curve data</div>

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#64748b', fontSize: 11 }}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 11 }}
          tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}K`}
          width={60}
        />
        <Tooltip
          contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
          formatter={(v, name) => [`₹${v.toLocaleString('en-IN')}`, name]}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="strategy"
          stroke="#6366f1"
          strokeWidth={2}
          dot={false}
          name="Strategy"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default function Backtest() {
  const { symbol } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleRun = () => {
    setLoading(true)
    setError(null)
    runBacktest(symbol)
      .then(setResult)
      .catch((e) => setError(e.response?.data?.detail ?? 'Backtest failed'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    handleRun()
  }, [symbol])

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(`/stock/${symbol}`)}
          className="text-slate-400 hover:text-slate-200 text-sm"
        >
          ← {symbol}
        </button>
        <h1 className="text-2xl font-bold text-slate-100">{symbol} Backtest</h1>
        <button
          onClick={handleRun}
          disabled={loading}
          className="ml-auto px-3 py-1 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm"
        >
          {loading ? 'Running…' : 'Re-run'}
        </button>
      </div>

      {loading && (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 bg-slate-800 rounded-xl animate-pulse" />
          ))}
          <p className="text-xs text-slate-500 text-center">
            Walk-forward backtest running — this may take 30-60 seconds…
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-950 border border-red-700 rounded-xl p-5 text-red-300 text-sm">
          {error}
        </div>
      )}

      {result && !loading && (
        <>
          {/* Summary banner */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-sm text-slate-300 font-mono">
            {result.summary}
          </div>

          {/* Equity curve */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Equity Curve (Strategy vs ₹1,00,000 initial)
            </div>
            <EquityChart equityCurve={result.equity_curve} />
          </div>

          {/* Metrics */}
          <MetricsTable metrics={result.metrics} />

          {/* Disclaimer */}
          <div className="bg-amber-950 border border-amber-700 rounded-xl p-4 text-xs text-amber-300">
            Walk-forward backtest — models are trained on rolling windows with no lookahead.
            However, past performance does not guarantee future results. Transaction costs of{' '}
            {((result.parameters?.transaction_cost ?? 0) * 100).toFixed(2)}% per trade are included.
          </div>
        </>
      )}
    </div>
  )
}
