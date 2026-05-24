const SIGNAL_STYLES = {
  BUY: {
    bg: 'bg-green-950',
    border: 'border-green-600',
    label: 'text-green-400',
    bar: 'bg-green-500',
  },
  SELL: {
    bg: 'bg-red-950',
    border: 'border-red-600',
    label: 'text-red-400',
    bar: 'bg-red-500',
  },
  HOLD: {
    bg: 'bg-yellow-950',
    border: 'border-yellow-600',
    label: 'text-yellow-400',
    bar: 'bg-yellow-500',
  },
}

/**
 * SignalCard — displays BUY/HOLD/SELL with probability bar and confidence.
 *
 * Props:
 *   signal        — 'BUY' | 'HOLD' | 'SELL'
 *   probability_up — float 0-1
 *   confidence     — float 0-1
 */
export default function SignalCard({ signal, probability_up, confidence }) {
  if (!signal) return null
  const styles = SIGNAL_STYLES[signal] || SIGNAL_STYLES.HOLD
  const probPct = Math.round((probability_up ?? 0.5) * 100)
  const confPct = Math.round((confidence ?? 0) * 100)

  return (
    <div className={`rounded-xl border p-5 ${styles.bg} ${styles.border}`}>
      <div className={`text-4xl font-black tracking-tight ${styles.label}`}>{signal}</div>

      <div className="mt-4">
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>Probability Up</span>
          <span>{probPct}%</span>
        </div>
        <div className="h-2 rounded-full bg-slate-700">
          <div
            className={`h-2 rounded-full ${styles.bar} transition-all duration-500`}
            style={{ width: `${probPct}%` }}
          />
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-400">
        Confidence:{' '}
        <span className="text-slate-200 font-medium">
          {confPct >= 70 ? 'High' : confPct >= 40 ? 'Medium' : 'Low'} ({confPct}%)
        </span>
      </div>
    </div>
  )
}
