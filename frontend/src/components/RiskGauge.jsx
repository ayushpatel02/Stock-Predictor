/**
 * RiskGauge — semicircular gauge showing risk score 1-10.
 * Uses SVG arc drawing; no external dependency.
 *
 * Props:
 *   score — integer 1-10
 */
export default function RiskGauge({ score }) {
  const s = Math.max(1, Math.min(10, score ?? 5))

  // SVG arc: semicircle from 180° to 0° (left to right)
  const r = 56
  const cx = 72
  const cy = 72
  const startAngle = Math.PI       // 180° (left)
  const endAngle = 0               // 0°   (right)
  const fraction = (s - 1) / 9    // 0 at score=1, 1 at score=10
  const angle = startAngle - fraction * Math.PI  // sweeps from left

  // Arc endpoint
  const x = cx + r * Math.cos(angle)
  const y = cy - r * Math.sin(angle)

  // Background arc (full semicircle)
  const bgX = cx + r  // rightmost point
  const bgY = cy

  // Color: green at 1, yellow at 5, red at 10
  const hue = Math.round(120 - (s - 1) * 12)
  const color = `hsl(${hue}, 80%, 50%)`

  const labelColor =
    s <= 3 ? 'text-green-400' : s <= 6 ? 'text-yellow-400' : 'text-red-400'

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="144" height="88" viewBox="0 0 144 88" aria-label={`Risk score ${s} out of 10`}>
        {/* Background track */}
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${bgX} ${bgY}`}
          fill="none"
          stroke="#334155"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Value arc */}
        {fraction > 0 && (
          <path
            d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${fraction > 0.5 ? 1 : 0} 1 ${x} ${y}`}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
          />
        )}
        {/* Score label */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          fontSize="28"
          fontWeight="bold"
          fill={color}
        >
          {s}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fontSize="10" fill="#94a3b8">
          /10
        </text>
        {/* Scale labels */}
        <text x={cx - r - 4} y={cy + 18} textAnchor="middle" fontSize="9" fill="#64748b">1</text>
        <text x={cx + r + 4} y={cy + 18} textAnchor="middle" fontSize="9" fill="#64748b">10</text>
      </svg>
      <span className={`text-xs font-semibold ${labelColor}`}>
        {s <= 3 ? 'Low Risk' : s <= 6 ? 'Medium Risk' : 'High Risk'}
      </span>
    </div>
  )
}
