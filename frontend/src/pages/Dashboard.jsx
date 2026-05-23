import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchMarketOverview, fetchPrediction, fetchUniverse } from '../api/client'
import MarketOverview from '../components/MarketOverview.jsx'

const SIGNAL_COLORS = {
  BUY: 'text-green-400 bg-green-950',
  SELL: 'text-red-400 bg-red-950',
  HOLD: 'text-yellow-400 bg-yellow-950',
}

function WatchlistRow({ symbol, onLoad }) {
  const [pred, setPred] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    fetchPrediction(symbol)
      .then(setPred)
      .catch(() => setPred(null))
      .finally(() => setLoading(false))
  }, [symbol])

  const signal = pred?.signal ?? '—'
  const prob = pred ? `${Math.round(pred.probability_up * 100)}%` : '—'
  const risk = pred?.risk_score ?? '—'
  const style = SIGNAL_COLORS[signal] ?? 'text-slate-400'

  return (
    <tr
      className="hover:bg-slate-700 cursor-pointer transition-colors"
      onClick={() => navigate(`/stock/${symbol}`)}
    >
      <td className="px-4 py-3 font-mono font-medium text-slate-100">{symbol}</td>
      <td className="px-4 py-3">
        {loading ? (
          <span className="text-slate-500 text-xs">loading…</span>
        ) : (
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${style}`}>{signal}</span>
        )}
      </td>
      <td className="px-4 py-3 text-slate-300 text-sm">{loading ? '…' : prob}</td>
      <td className="px-4 py-3 text-slate-300 text-sm">{loading ? '…' : risk}</td>
    </tr>
  )
}

export default function Dashboard() {
  const [market, setMarket] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [marketLoading, setMarketLoading] = useState(true)

  useEffect(() => {
    fetchMarketOverview()
      .then(setMarket)
      .catch(() => setMarket(null))
      .finally(() => setMarketLoading(false))

    fetchUniverse()
      .then((d) => setSymbols(d.symbols ?? []))
      .catch(() => setSymbols([]))
  }, [])

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
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

      <section>
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Nifty 50 Watchlist
        </h2>
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-400 border-b border-slate-700">
                <th className="px-4 py-2 text-left">Symbol</th>
                <th className="px-4 py-2 text-left">Signal</th>
                <th className="px-4 py-2 text-left">Prob Up</th>
                <th className="px-4 py-2 text-left">Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {symbols.map((sym) => (
                <WatchlistRow key={sym} symbol={sym} />
              ))}
              {symbols.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                    Could not load universe — is the backend running?
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-2">
          Signals require trained models. Run{' '}
          <code className="font-mono bg-slate-800 px-1 rounded">python -m app.scripts.train_all</code>{' '}
          first.
        </p>
      </section>
    </div>
  )
}
