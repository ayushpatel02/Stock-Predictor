import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchDvm, fetchOverview, fetchPrediction, fetchStock, fetchTechnicals } from '../api/client'
import ConsensusChart from '../components/ConsensusChart.jsx'
import DvmCard from '../components/DvmCard.jsx'
import ForecastChart from '../components/ForecastChart.jsx'
import NewsFeed from '../components/NewsFeed.jsx'
import PeersTable from '../components/PeersTable.jsx'
import PriceChart from '../components/PriceChart.jsx'
import PriceChartWithPE from '../components/PriceChartWithPE.jsx'
import RiskGauge from '../components/RiskGauge.jsx'
import SignalCard from '../components/SignalCard.jsx'
import StockPriceAnalysis from '../components/StockPriceAnalysis.jsx'
import TechAnalysisPanel from '../components/TechAnalysisPanel.jsx'

const TABS = ['Overview', 'Technicals', 'Fundamentals', 'News', 'Peers']

function FundamentalsTable({ data }) {
  if (!data) return null
  const fmt = (v, kind = 'num') => {
    if (v == null) return '—'
    if (kind === 'pct') return `${(v * 100).toFixed(1)}%`
    if (kind === 'money') return `₹${(v / 1e9).toFixed(2)}B`
    if (kind === 'ratio') return v.toFixed(2)
    return v.toFixed(2)
  }
  const rows = [
    ['P/E Ratio', fmt(data.pe_ratio, 'ratio')],
    ['EPS', fmt(data.eps, 'ratio')],
    ['ROE', fmt(data.roe, 'pct')],
    ['Profit Margins', fmt(data.profit_margins, 'pct')],
    ['Debt/Equity', fmt(data.debt_to_equity, 'ratio')],
    ['Beta', fmt(data.beta, 'ratio')],
    ['Price/Book', fmt(data.price_to_book, 'ratio')],
    ['Book Value', fmt(data.book_value, 'ratio')],
    ['Dividend Yield', fmt(data.dividend_yield, 'pct')],
    ['Revenue Growth', fmt(data.revenue_growth, 'pct')],
    ['52W High', fmt(data.week_52_high, 'ratio')],
    ['52W Low', fmt(data.week_52_low, 'ratio')],
    ['Market Cap', fmt(data.market_cap, 'money')],
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
              <td className="px-4 py-2 text-slate-100 text-right font-mono">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TechnicalsTable({ ohlcv }) {
  if (!ohlcv?.length) return null
  const closes = ohlcv.map((d) => d.close)
  const volumes = ohlcv.map((d) => d.volume)
  const last = closes[closes.length - 1]
  const first = closes[0]
  const high30 = Math.max(...closes)
  const low30 = Math.min(...closes)
  const avgVol = volumes.reduce((a, b) => a + b, 0) / volumes.length
  const monthReturn = ((last - first) / first) * 100

  const rows = [
    ['Last Close', `₹${last.toFixed(2)}`],
    ['30d High', `₹${high30.toFixed(2)}`],
    ['30d Low', `₹${low30.toFixed(2)}`],
    ['30d Return', `${monthReturn >= 0 ? '+' : ''}${monthReturn.toFixed(2)}%`],
    ['Avg Daily Volume', avgVol.toLocaleString('en-IN', { maximumFractionDigits: 0 })],
  ]
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider">
        30-Day Price Stats
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

export default function StockDetail() {
  const { symbol } = useParams()
  const navigate = useNavigate()
  const [stock, setStock] = useState(null)
  const [prediction, setPrediction] = useState(null)
  const [dvm, setDvm] = useState(null)
  const [overview, setOverview] = useState(null)
  const [technicals, setTechnicals] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('Overview')
  const [techLoading, setTechLoading] = useState(false)
  const [overviewLoading, setOverviewLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setOverview(null)
    setTechnicals(null)
    Promise.allSettled([
      fetchStock(symbol),
      fetchPrediction(symbol),
      fetchDvm(symbol),
    ]).then(([stockRes, predRes, dvmRes]) => {
      if (stockRes.status === 'fulfilled') setStock(stockRes.value)
      else setError(stockRes.reason?.response?.data?.detail ?? 'Failed to load stock data')
      if (predRes.status === 'fulfilled') setPrediction(predRes.value)
      if (dvmRes.status === 'fulfilled') setDvm(dvmRes.value)
      setLoading(false)
    })
  }, [symbol])

  // Lazy-load overview when tab is selected
  useEffect(() => {
    if (tab === 'Overview' && !overview && !overviewLoading) {
      setOverviewLoading(true)
      fetchOverview(symbol)
        .then(setOverview)
        .catch(() => setOverview(null))
        .finally(() => setOverviewLoading(false))
    }
  }, [tab, symbol]) // eslint-disable-line react-hooks/exhaustive-deps

  // Lazy-load technicals when tab is selected
  useEffect(() => {
    if (tab === 'Technicals' && !technicals && !techLoading) {
      setTechLoading(true)
      fetchTechnicals(symbol)
        .then(setTechnicals)
        .catch(() => setTechnicals(null))
        .finally(() => setTechLoading(false))
    }
  }, [tab, symbol]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-4">
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
        <button onClick={() => navigate('/')} className="mt-4 text-sm text-indigo-400 hover:text-indigo-300">
          ← Back to Dashboard
        </button>
      </div>
    )
  }

  const latest = stock?.ohlcv?.[stock.ohlcv.length - 1]
  const prev = stock?.ohlcv?.[stock.ohlcv.length - 2]
  const dayPct = latest && prev ? ((latest.close - prev.close) / prev.close) * 100 : 0
  const isUp = dayPct >= 0

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end gap-4">
        <button onClick={() => navigate('/')} className="text-slate-400 hover:text-slate-200 text-sm">
          ← Dashboard
        </button>
        <div>
          <h1 className="text-3xl font-bold text-slate-100 leading-none">{symbol}</h1>
          {latest && (
            <div className="flex items-baseline gap-3 mt-1">
              <span className="text-2xl font-bold text-slate-200">₹{latest.close.toFixed(2)}</span>
              <span className={`text-sm font-semibold ${isUp ? 'text-green-400' : 'text-red-400'}`}>
                {isUp ? '+' : ''}{dayPct.toFixed(2)}%
              </span>
            </div>
          )}
        </div>
        {prediction?.as_of && (
          <span className="text-xs text-slate-500 ml-auto">
            As of {new Date(prediction.as_of).toLocaleString()}
          </span>
        )}
      </div>

      {/* DVM Card — always visible */}
      <DvmCard
        durability={dvm?.durability}
        valuation={dvm?.valuation}
        momentum={dvm?.momentum}
        breakdown={dvm?.dvm_breakdown}
      />

      {/* Tabs */}
      <div className="border-b border-slate-700 flex gap-1 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap ${
              tab === t
                ? 'text-indigo-400 border-b-2 border-indigo-400 -mb-px'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ── */}
      {tab === 'Overview' && (
        <div className="space-y-5">
          {overviewLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => <div key={i} className="h-40 bg-slate-800 rounded-xl animate-pulse" />)}
            </div>
          ) : (
            <>
              <StockPriceAnalysis data={overview?.price_analysis} />

              <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  Price Chart with P/E Overlay
                </div>
                <PriceChartWithPE peHistory={overview?.pe_history} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ForecastChart
                  title="Revenue Forecast"
                  actuals={overview?.revenue_forecast?.actuals ?? []}
                  estimates={overview?.revenue_forecast?.estimates ?? []}
                  formatValue={(v) => v != null ? `₹${(v / 1e9).toFixed(1)}B` : '—'}
                />
                <ForecastChart
                  title="EPS Forecast"
                  actuals={overview?.eps_forecast?.actuals ?? []}
                  estimates={overview?.eps_forecast?.estimates ?? []}
                  formatValue={(v) => v != null ? `₹${Number(v).toFixed(2)}` : '—'}
                />
              </div>

              <ConsensusChart consensus={overview?.consensus} />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {prediction ? (
                  <SignalCard
                    signal={prediction.signal}
                    probability_up={prediction.probability_up}
                    confidence={prediction.confidence}
                  />
                ) : (
                  <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 text-slate-400 text-sm">
                    No prediction — model not trained.
                  </div>
                )}
                <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex flex-col items-center justify-center gap-2">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Risk Score
                  </div>
                  <RiskGauge score={prediction?.risk_score ?? 5} />
                </div>
              </div>

              <button
                onClick={() => navigate(`/backtest/${symbol}`)}
                className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
              >
                Run Walk-Forward Backtest →
              </button>
            </>
          )}
        </div>
      )}

      {/* ── Technicals Tab ── */}
      {tab === 'Technicals' && (
        <div className="space-y-4">
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Price History
            </div>
            <PriceChart data={stock?.ohlcv ?? []} />
          </div>

          <TechnicalsTable ohlcv={stock?.ohlcv} />

          {techLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 bg-slate-800 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : (
            <TechAnalysisPanel data={technicals} />
          )}
        </div>
      )}

      {tab === 'Fundamentals' && (
        <FundamentalsTable data={stock?.fundamentals} />
      )}

      {tab === 'News' && <NewsFeed symbol={symbol} limit={12} />}

      {tab === 'Peers' && <PeersTable symbol={symbol} n={6} />}
    </div>
  )
}
