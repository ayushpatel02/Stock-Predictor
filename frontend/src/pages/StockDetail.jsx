import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchPrediction, fetchStock } from '../api/client'
import PriceChart from '../components/PriceChart.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import SignalCard from '../components/SignalCard.jsx'

function FundamentalsTable({ data }) {
  if (!data) return null
  const rows = [
    ['P/E Ratio', data.pe_ratio?.toFixed(2) ?? '—'],
    ['EPS', data.eps?.toFixed(2) ?? '—'],
    ['ROE', data.roe != null ? `${(data.roe * 100).toFixed(1)}%` : '—'],
    ['Debt/Equity', data.debt_to_equity?.toFixed(2) ?? '—'],
    ['Beta', data.beta?.toFixed(2) ?? '—'],
    ['52W High', data.week_52_high?.toFixed(2) ?? '—'],
    ['52W Low', data.week_52_low?.toFixed(2) ?? '—'],
    ['Market Cap', data.market_cap ? `₹${(data.market_cap / 1e9).toFixed(0)}B` : '—'],
  ]

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Fundamentals
      </div>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-slate-700">
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td className="px-4 py-2 text-slate-400">{label}</td>
              <td className="px-4 py-2 text-slate-100 text-right">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function StockDetail() {
  const { symbol } = useParams()
  const navigate = useNavigate()
  const [stock, setStock] = useState(null)
  const [prediction, setPrediction] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.allSettled([fetchStock(symbol), fetchPrediction(symbol)]).then(([stockRes, predRes]) => {
      if (stockRes.status === 'fulfilled') setStock(stockRes.value)
      else setError(stockRes.reason?.response?.data?.detail ?? 'Failed to load stock data')
      if (predRes.status === 'fulfilled') setPrediction(predRes.value)
      setLoading(false)
    })
  }, [symbol])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-slate-800 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="bg-red-950 border border-red-700 rounded-xl p-6 text-red-300">
          <div className="font-bold mb-1">Error loading {symbol}</div>
          <div className="text-sm">{error}</div>
        </div>
        <button
          onClick={() => navigate('/')}
          className="mt-4 text-sm text-indigo-400 hover:text-indigo-300"
        >
          ← Back to Dashboard
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/')} className="text-slate-400 hover:text-slate-200 text-sm">
          ← Dashboard
        </button>
        <h1 className="text-2xl font-bold text-slate-100">{symbol}</h1>
        {prediction?.as_of && (
          <span className="text-xs text-slate-500 ml-auto">
            As of {new Date(prediction.as_of).toLocaleString()}
          </span>
        )}
      </div>

      {/* Price chart */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Price History
        </div>
        <PriceChart data={stock?.ohlcv ?? []} />
      </div>

      {/* Signal + Risk */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          {prediction ? (
            <SignalCard
              signal={prediction.signal}
              probability_up={prediction.probability_up}
              confidence={prediction.confidence}
            />
          ) : (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 text-slate-400 text-sm">
              No prediction available — model not trained yet.
            </div>
          )}
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex flex-col items-center justify-center gap-2">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Risk Score
          </div>
          <RiskGauge score={prediction?.risk_score ?? 5} />
        </div>
      </div>

      {/* Fundamentals + Backtest button */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FundamentalsTable data={stock?.fundamentals} />
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex flex-col gap-3">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Backtest
          </div>
          <p className="text-sm text-slate-400">
            Run a walk-forward backtest on 5 years of data to see how the model performed historically.
          </p>
          <button
            onClick={() => navigate(`/backtest/${symbol}`)}
            className="mt-auto w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
          >
            Run Backtest →
          </button>
        </div>
      </div>
    </div>
  )
}
