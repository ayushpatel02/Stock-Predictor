/**
 * DvmCard — Trendlyne-style Durability / Valuation / Momentum scores.
 *
 * Each score is a 0-100 number shown as a circular gauge with color coding:
 *   ≥70 green (strong)  · 40-70 amber (average)  · <40 red (weak)
 *
 * Props:
 *   durability, valuation, momentum — numbers 0-100
 *   breakdown (optional) — { durability: {...}, valuation: {...}, momentum: {...} }
 */
const COLORS = {
  strong: { ring: '#16a34a', text: 'text-green-400', bg: 'bg-green-950/50' },
  average: { ring: '#f59e0b', text: 'text-amber-400', bg: 'bg-amber-950/50' },
  weak: { ring: '#dc2626', text: 'text-red-400', bg: 'bg-red-950/50' },
}

function tierFor(score) {
  if (score >= 70) return 'strong'
  if (score >= 40) return 'average'
  return 'weak'
}

function ScoreRing({ score, label, sublabel }) {
  const tier = tierFor(score)
  const c = COLORS[tier]
  const radius = 36
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference

  return (
    <div className={`flex flex-col items-center gap-2 p-3 rounded-lg ${c.bg}`}>
      <svg width="96" height="96" className="-rotate-90">
        {/* Track */}
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke="#1e293b"
          strokeWidth="8"
        />
        {/* Score arc */}
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke={c.ring}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease-out' }}
        />
        {/* Score text — rotate back to upright */}
        <text
          x="48"
          y="48"
          textAnchor="middle"
          dominantBaseline="central"
          transform="rotate(90 48 48)"
          fontSize="22"
          fontWeight="bold"
          fill={c.ring}
        >
          {Math.round(score)}
        </text>
      </svg>
      <div className="text-center">
        <div className="text-sm font-semibold text-slate-200">{label}</div>
        {sublabel && (
          <div className={`text-xs font-medium ${c.text}`}>{sublabel}</div>
        )}
      </div>
    </div>
  )
}

function tierLabel(score) {
  if (score >= 80) return 'Excellent'
  if (score >= 70) return 'Strong'
  if (score >= 55) return 'Above average'
  if (score >= 40) return 'Average'
  if (score >= 25) return 'Weak'
  return 'Very weak'
}

export default function DvmCard({ durability, valuation, momentum, breakdown }) {
  if (durability == null) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-slate-400 text-sm">
        DVM scores unavailable
      </div>
    )
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          DVM Scores
        </div>
        <div className="text-xs text-slate-500">Durability · Valuation · Momentum</div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <ScoreRing
          score={durability}
          label="Durability"
          sublabel={tierLabel(durability)}
        />
        <ScoreRing
          score={valuation}
          label="Valuation"
          sublabel={tierLabel(valuation)}
        />
        <ScoreRing
          score={momentum}
          label="Momentum"
          sublabel={tierLabel(momentum)}
        />
      </div>
      {breakdown && (
        <details className="mt-3 text-xs text-slate-400">
          <summary className="cursor-pointer hover:text-slate-200">
            Show breakdown
          </summary>
          <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
            {Object.entries(breakdown).map(([category, parts]) => (
              <div key={category} className="bg-slate-900/50 rounded p-2">
                <div className="font-semibold text-slate-300 capitalize mb-1">
                  {category}
                </div>
                {Object.entries(parts).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <span className="truncate text-slate-500">{k}</span>
                    <span className="text-slate-300 font-mono">
                      {Math.round(v)}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
