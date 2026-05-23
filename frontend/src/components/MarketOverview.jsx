/**
 * MarketOverview — 4-card grid showing Nifty 50, Bank Nifty, VIX, Sensex.
 *
 * Props:
 *   data — object from /market/overview endpoint
 */
const INDEX_META = {
  nifty50: { label: 'Nifty 50', emoji: null },
  banknifty: { label: 'Bank Nifty', emoji: null },
  vix: { label: 'India VIX', emoji: null },
  sensex: { label: 'Sensex', emoji: null },
}

function IndexCard({ name, entry }) {
  const meta = INDEX_META[name] ?? { label: name }
  if (!entry) {
    return (
      <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
        <div className="text-xs text-slate-400">{meta.label}</div>
        <div className="text-slate-500 text-sm mt-1">Unavailable</div>
      </div>
    )
  }

  const isUp = entry.change_pct >= 0
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <div className="text-xs text-slate-400">{meta.label}</div>
      <div className="text-xl font-bold text-slate-100 mt-1">
        {entry.price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
      </div>
      <div className={`text-sm font-medium mt-1 ${isUp ? 'text-green-400' : 'text-red-400'}`}>
        {isUp ? '+' : ''}{entry.change_pct.toFixed(2)}%
      </div>
    </div>
  )
}

export default function MarketOverview({ data }) {
  if (!data) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {['nifty50', 'banknifty', 'vix', 'sensex'].map((k) => (
          <div key={k} className="bg-slate-800 rounded-xl p-4 border border-slate-700 animate-pulse h-20" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {Object.entries(data).map(([name, entry]) => (
        <IndexCard key={name} name={name} entry={entry} />
      ))}
    </div>
  )
}
