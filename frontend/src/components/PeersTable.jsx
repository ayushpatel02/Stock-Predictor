import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchPeers } from '../api/client'

/**
 * PeersTable — shows N peer stocks for comparison.
 * Peer selection is by market cap proximity (yfinance doesn't reliably
 * return sector for Indian stocks).
 */
export default function PeersTable({ symbol, n = 5 }) {
  const [peers, setPeers] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    fetchPeers(symbol, n)
      .then((d) => setPeers(d.peers ?? []))
      .catch(() => setPeers([]))
      .finally(() => setLoading(false))
  }, [symbol, n])

  if (loading) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Peers
        </div>
        <div className="space-y-2">
          {Array.from({ length: n }).map((_, i) => (
            <div key={i} className="h-8 bg-slate-900/50 rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Peers (by market cap)
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-slate-500 border-b border-slate-700">
            <th className="px-4 py-2 text-left font-medium">Symbol</th>
            <th className="px-4 py-2 text-right font-medium">Price</th>
            <th className="px-4 py-2 text-right font-medium">Day %</th>
            <th className="px-4 py-2 text-right font-medium">P/E</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700">
          {(peers ?? []).map((p) => {
            const pct = (p.day_return ?? 0) * 100
            const isUp = pct >= 0
            return (
              <tr
                key={p.symbol}
                onClick={() => navigate(`/stock/${p.symbol}`)}
                className="hover:bg-slate-700/50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-2 font-mono font-medium text-slate-200">
                  {p.symbol}
                </td>
                <td className="px-4 py-2 text-right text-slate-300">
                  ₹{p.price?.toFixed(2) ?? '—'}
                </td>
                <td className={`px-4 py-2 text-right font-medium ${isUp ? 'text-green-400' : 'text-red-400'}`}>
                  {isUp ? '+' : ''}{pct.toFixed(2)}%
                </td>
                <td className="px-4 py-2 text-right text-slate-400">
                  {p.pe_ratio != null ? p.pe_ratio.toFixed(1) : '—'}
                </td>
              </tr>
            )
          })}
          {(!peers || peers.length === 0) && (
            <tr>
              <td colSpan={4} className="px-4 py-4 text-center text-slate-500 text-sm">
                No peer data available
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
