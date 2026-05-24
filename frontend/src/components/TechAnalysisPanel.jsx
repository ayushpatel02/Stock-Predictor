/**
 * TechAnalysisPanel — TradingView-style technical analysis.
 *
 * Shows an overall summary speedometer gauge, oscillators section with its
 * own mini gauge + table, and a moving averages section with mini gauge + table.
 *
 * Props:
 *   data — response from GET /stocks/{symbol}/technicals
 */

const ACTION_STYLES = {
  BUY: 'bg-green-900/60 text-green-300 border border-green-700',
  SELL: 'bg-red-900/60 text-red-300 border border-red-700',
  NEUTRAL: 'bg-slate-700 text-slate-400 border border-slate-600',
}

const REC_COLORS = {
  'STRONG BUY': '#16a34a',
  BUY: '#22c55e',
  NEUTRAL: '#94a3b8',
  SELL: '#f97316',
  'STRONG SELL': '#dc2626',
}

const REC_TEXT_COLORS = {
  'STRONG BUY': 'text-green-500',
  BUY: 'text-green-400',
  NEUTRAL: 'text-slate-400',
  SELL: 'text-orange-400',
  'STRONG SELL': 'text-red-500',
}

// Speedometer SVG gauge — semicircle with 5 zones and a needle
function SpeedometerGauge({ buy, sell, neutral, recommendation, size = 'large' }) {
  const total = buy + sell + neutral
  const isLarge = size === 'large'
  const w = isLarge ? 220 : 150
  const h = isLarge ? 130 : 90
  const cx = w / 2
  const cy = isLarge ? 110 : 78
  const r = isLarge ? 85 : 58

  // Needle angle: -90° (strong sell) to +90° (strong buy)
  // Map buy% to angle
  const netScore = total > 0 ? (buy - sell) / total : 0  // -1 to +1
  const needleAngle = netScore * 85  // degrees from vertical down, -85 to +85

  const toRad = (deg) => (deg * Math.PI) / 180
  const arcPoint = (angleDeg) => {
    const rad = toRad(angleDeg - 90)  // offset so 0° = top
    return {
      x: cx + r * Math.cos(rad),
      y: cy + r * Math.sin(rad),
    }
  }

  // 5 zones: Strong Sell(-90), Sell(-54), Neutral(-18 to +18), Buy(+54), Strong Buy(+90)
  const zones = [
    { from: -90, to: -54, color: '#dc2626' },
    { from: -54, to: -18, color: '#f97316' },
    { from: -18, to: 18, color: '#94a3b8' },
    { from: 18, to: 54, color: '#22c55e' },
    { from: 54, to: 90, color: '#16a34a' },
  ]

  const arcPath = (fromDeg, toDeg) => {
    const p1 = arcPoint(fromDeg)
    const p2 = arcPoint(toDeg)
    const largeArc = Math.abs(toDeg - fromDeg) > 180 ? 1 : 0
    return `M ${p1.x} ${p1.y} A ${r} ${r} 0 ${largeArc} 1 ${p2.x} ${p2.y}`
  }

  // Needle: from center to rim
  const needleRad = toRad(needleAngle - 90)
  const needleX = cx + (r - 12) * Math.cos(needleRad)
  const needleY = cy + (r - 12) * Math.sin(needleRad)
  const recColor = REC_COLORS[recommendation] || '#94a3b8'

  const labelSize = isLarge ? 13 : 10
  const recFontSize = isLarge ? 16 : 11
  const countFontSize = isLarge ? 12 : 9

  return (
    <div className="flex flex-col items-center">
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
        {/* Track (background) */}
        <path
          d={arcPath(-90, 90)}
          fill="none"
          stroke="#1e293b"
          strokeWidth={isLarge ? 14 : 10}
          strokeLinecap="round"
        />
        {/* Colored zones */}
        {zones.map((z, i) => (
          <path
            key={i}
            d={arcPath(z.from, z.to)}
            fill="none"
            stroke={z.color}
            strokeWidth={isLarge ? 14 : 10}
            opacity={0.7}
          />
        ))}
        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke={recColor}
          strokeWidth={isLarge ? 3 : 2}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={isLarge ? 5 : 4} fill={recColor} />
        {/* Zone labels */}
        {isLarge && (
          <>
            <text x={cx - r - 6} y={cy + 16} textAnchor="end" fontSize={labelSize - 2} fill="#dc2626">S.Sell</text>
            <text x={cx + r + 6} y={cy + 16} textAnchor="start" fontSize={labelSize - 2} fill="#16a34a">S.Buy</text>
          </>
        )}
        {/* Recommendation text */}
        <text
          x={cx}
          y={cy - (isLarge ? 24 : 16)}
          textAnchor="middle"
          fontSize={recFontSize}
          fontWeight="bold"
          fill={recColor}
        >
          {recommendation}
        </text>
        {/* Counts */}
        <text x={cx} y={cy - (isLarge ? 6 : 4)} textAnchor="middle" fontSize={countFontSize} fill="#64748b">
          {buy}B · {neutral}N · {sell}S
        </text>
      </svg>
    </div>
  )
}

function IndicatorTable({ indicators }) {
  if (!indicators?.length) return null
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-xs text-slate-500 border-b border-slate-700">
          <th className="px-3 py-1.5 text-left font-medium">Indicator</th>
          <th className="px-3 py-1.5 text-right font-medium">Value</th>
          <th className="px-3 py-1.5 text-right font-medium">Action</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-700/50">
        {indicators.map((ind) => (
          <tr key={ind.name} className="hover:bg-slate-700/30">
            <td className="px-3 py-1.5 text-slate-300 text-xs font-mono">{ind.name}</td>
            <td className="px-3 py-1.5 text-right text-slate-400 text-xs font-mono">
              {ind.value != null ? ind.value : '—'}
            </td>
            <td className="px-3 py-1.5 text-right">
              <span className={`px-2 py-0.5 rounded text-xs font-bold ${ACTION_STYLES[ind.action] || ACTION_STYLES.NEUTRAL}`}>
                {ind.action}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function TechAnalysisPanel({ data }) {
  if (!data) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 text-center text-slate-500 text-sm">
        Technical analysis data unavailable
      </div>
    )
  }

  const { oscillators, moving_averages, summary } = data
  const recTextCls = REC_TEXT_COLORS[summary?.recommendation] || 'text-slate-400'

  return (
    <div className="space-y-4">
      {/* Overall Summary */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">
          Overall Summary — {summary?.total ?? 0} Indicators
        </div>
        <SpeedometerGauge
          buy={summary?.buy ?? 0}
          sell={summary?.sell ?? 0}
          neutral={summary?.neutral ?? 0}
          recommendation={summary?.recommendation ?? 'NEUTRAL'}
          size="large"
        />
        <div className="flex justify-center gap-6 mt-3 text-xs">
          <span className="text-green-400 font-semibold">{summary?.buy ?? 0} Buy</span>
          <span className="text-slate-400">{summary?.neutral ?? 0} Neutral</span>
          <span className="text-red-400 font-semibold">{summary?.sell ?? 0} Sell</span>
        </div>
      </div>

      {/* Oscillators */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Oscillators
          </div>
          <SpeedometerGauge
            buy={oscillators?.summary?.buy ?? 0}
            sell={oscillators?.summary?.sell ?? 0}
            neutral={oscillators?.summary?.neutral ?? 0}
            recommendation={oscillators?.summary?.recommendation ?? 'NEUTRAL'}
            size="small"
          />
        </div>
        <IndicatorTable indicators={oscillators?.indicators} />
      </div>

      {/* Moving Averages */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Moving Averages
          </div>
          <SpeedometerGauge
            buy={moving_averages?.summary?.buy ?? 0}
            sell={moving_averages?.summary?.sell ?? 0}
            neutral={moving_averages?.summary?.neutral ?? 0}
            recommendation={moving_averages?.summary?.recommendation ?? 'NEUTRAL'}
            size="small"
          />
        </div>
        <IndicatorTable indicators={moving_averages?.indicators} />
      </div>
    </div>
  )
}
