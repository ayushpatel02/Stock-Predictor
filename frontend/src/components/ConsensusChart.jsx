/**
 * ConsensusChart — analyst consensus recommendation visualization.
 *
 * Shows a horizontal stacked bar (Strong Buy → Strong Sell) with
 * analyst counts, overall recommendation label, and target price range.
 *
 * Props:
 *   consensus — object from /overview endpoint
 *     { strong_buy, buy, hold, sell, strong_sell, total, recommendation,
 *       mean, high, low, current }
 */

const SEGMENTS = [
  { key: 'strong_buy', label: 'Strong Buy', color: '#16a34a' },
  { key: 'buy', label: 'Buy', color: '#22c55e' },
  { key: 'hold', label: 'Hold', color: '#f59e0b' },
  { key: 'sell', label: 'Sell', color: '#f97316' },
  { key: 'strong_sell', label: 'Strong Sell', color: '#dc2626' },
]

const REC_COLORS = {
  'Strong Buy': 'text-green-500',
  Buy: 'text-green-400',
  Hold: 'text-amber-400',
  Sell: 'text-orange-400',
  'Strong Sell': 'text-red-500',
  Neutral: 'text-slate-400',
}

function fmt(v) {
  if (v == null) return '—'
  return `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

export default function ConsensusChart({ consensus }) {
  if (!consensus) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
          Analyst Consensus
        </div>
        <div className="text-sm text-slate-500 py-4 text-center">No analyst data available</div>
      </div>
    )
  }

  const total = consensus.total || 1
  const rec = consensus.recommendation
  const recColor = REC_COLORS[rec] || 'text-slate-400'

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Analyst Consensus
        </div>
        <div className="text-right">
          <div className={`text-base font-bold ${recColor}`}>{rec ?? 'N/A'}</div>
          <div className="text-xs text-slate-500">{consensus.total ?? 0} analysts</div>
        </div>
      </div>

      {/* Stacked horizontal bar */}
      <div className="flex rounded-full overflow-hidden h-5 mb-3 gap-px">
        {SEGMENTS.map((seg) => {
          const count = consensus[seg.key] || 0
          const pct = (count / total) * 100
          if (pct < 0.5) return null
          return (
            <div
              key={seg.key}
              style={{ width: `${pct}%`, backgroundColor: seg.color }}
              title={`${seg.label}: ${count} (${pct.toFixed(0)}%)`}
              className="transition-all duration-500"
            />
          )
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-4">
        {SEGMENTS.map((seg) => {
          const count = consensus[seg.key] || 0
          return (
            <div key={seg.key} className="flex items-center gap-1.5 text-xs text-slate-400">
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: seg.color }} />
              <span>{seg.label}</span>
              <span className="font-mono text-slate-300 font-semibold">{count}</span>
            </div>
          )
        })}
      </div>

      {/* Target price range */}
      {(consensus.mean || consensus.high || consensus.low) && (
        <div className="border-t border-slate-700 pt-3 mt-1">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Price Target Range
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">Low {fmt(consensus.low)}</span>
            {/* Range bar */}
            <div className="flex-1 relative h-2 bg-slate-700 rounded-full">
              {consensus.low && consensus.high && consensus.mean && (
                <>
                  {/* Mean marker */}
                  <div
                    className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-indigo-400 border-2 border-slate-800 -translate-x-1/2"
                    style={{
                      left: `${((consensus.mean - consensus.low) / (consensus.high - consensus.low)) * 100}%`,
                    }}
                    title={`Mean: ${fmt(consensus.mean)}`}
                  />
                </>
              )}
            </div>
            <span className="text-xs text-slate-500">High {fmt(consensus.high)}</span>
          </div>
          {consensus.mean && (
            <div className="text-center mt-1.5 text-xs text-indigo-400 font-semibold">
              Mean target: {fmt(consensus.mean)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
